"""FastAPI backend — tüm endpoint'ler /api/ prefix'i altında.

Auth: /api/login hariç tüm endpoint'ler JWT token ister.
React build: /build dizininden serve edilir (SPA fallback dahil).
"""
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import (
    init_db,
    # Publisher
    get_all_publishers, add_publisher, get_publisher,
    update_publisher as db_update_publisher,
    delete_publisher as db_delete_publisher,
    # App
    add_app, get_apps_by_publisher, get_app,
    update_app as db_update_app, delete_app as db_delete_app,
    # Slot
    get_slot_cache,
    # Snapshot
    get_snapshots, get_snapshot, mark_snapshot_rolled_back,
    # Logs
    get_job_logs, log_operation,
    # Approvals
    get_approval, approve_job, get_pending_approvals,
)
from engine import sync_app, rollback_snapshot
from scheduler import start_scheduler
from auth import authenticate, auth_middleware

app = FastAPI()

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(auth_middleware)

init_db()
start_scheduler()

# In-memory job tracker
jobs = {}


def mask_key(key: str) -> str:
    if not key or len(key) <= 6:
        return "***"
    return "***" + key[-6:]


# --- API Router ---
api = APIRouter(prefix="/api")


# === Auth ===

class LoginRequest(BaseModel):
    email: str
    password: str


@api.post("/login")
def login(req: LoginRequest):
    token = authenticate(req.email, req.password)
    if not token:
        return {"error": "Gecersiz email veya sifre"}
    return {"token": token, "email": req.email}


# === Publishers ===

class PublisherCreate(BaseModel):
    name: str
    management_key: str
    gam_publisher_id: str
    frequency_days: int = 2
    mode: str = "manual"
    notify_email: str = ""


class PublisherUpdate(BaseModel):
    active: Optional[int] = None
    frequency_days: Optional[int] = None
    mode: Optional[str] = None
    notify_email: Optional[str] = None
    gam_publisher_id: Optional[str] = None


@api.get("/publishers")
def list_publishers():
    publishers = get_all_publishers()
    for p in publishers:
        p["management_key"] = mask_key(p["management_key"])
    return publishers


@api.post("/publishers")
def create_publisher(p: PublisherCreate):
    publisher_id = add_publisher(
        name=p.name,
        management_key=p.management_key,
        gam_publisher_id=p.gam_publisher_id,
        frequency_days=p.frequency_days,
        mode=p.mode,
        notify_email=p.notify_email,
    )
    return {"id": publisher_id, "status": "created"}


@api.put("/publishers/{publisher_id}")
def update_publisher(publisher_id: int, p: PublisherUpdate):
    found = db_update_publisher(
        publisher_id,
        active=p.active, frequency_days=p.frequency_days,
        mode=p.mode, notify_email=p.notify_email,
        gam_publisher_id=p.gam_publisher_id,
    )
    if not found:
        return {"error": "Publisher not found"}
    return {"status": "updated"}


@api.delete("/publishers/{publisher_id}")
def delete_publisher(publisher_id: int):
    found = db_delete_publisher(publisher_id)
    if not found:
        return {"error": "Publisher not found"}
    return {"status": "deleted"}


@api.get("/publishers/{publisher_id}/apps")
def list_publisher_apps(publisher_id: int):
    return get_apps_by_publisher(publisher_id)


# === Apps ===

class AppCreate(BaseModel):
    publisher_id: int
    label: str
    gam_app_name: str
    platform: str  # aos | ios


class AppUpdate(BaseModel):
    label: Optional[str] = None
    gam_app_name: Optional[str] = None
    platform: Optional[str] = None
    active: Optional[int] = None


@api.post("/apps")
def create_app(a: AppCreate):
    if a.platform not in ("aos", "ios"):
        return {"error": "Platform 'aos' veya 'ios' olmali"}
    app_id = add_app(a.publisher_id, a.label, a.gam_app_name, a.platform)
    return {"id": app_id, "status": "created"}


@api.get("/apps/{app_id}")
def get_app_detail(app_id: int):
    a = get_app(app_id)
    if not a:
        return {"error": "App not found"}
    return a


@api.put("/apps/{app_id}")
def update_app(app_id: int, a: AppUpdate):
    found = db_update_app(
        app_id, label=a.label, gam_app_name=a.gam_app_name,
        platform=a.platform, active=a.active,
    )
    if not found:
        return {"error": "App not found"}
    return {"status": "updated"}


@api.delete("/apps/{app_id}")
def delete_app(app_id: int):
    found = db_delete_app(app_id)
    if not found:
        return {"error": "App not found"}
    return {"status": "deleted"}


@api.get("/apps/{app_id}/slot-status")
def get_app_slot_status(app_id: int):
    """Slot cache'i döndür (GAM'den en son senkronize edilmiş durum)."""
    a = get_app(app_id)
    if not a:
        return {"error": "App not found"}
    slots = get_slot_cache(app_id)
    return {"app": a, "slots": slots}


# === Run ===

def _run_sync(job_id: str, app: dict, dry_run: bool):
    """Background thread'de sync çalıştırır, sonuçları jobs dict'ine yazar."""
    try:
        result = sync_app(app, run_job_id=job_id, dry_run=dry_run)
        jobs[job_id] = {
            **result,
            "status": result.get("status", "done"),
            "success": result.get("success", 0) if not dry_run else result.get("matched", 0),
        }
    except Exception as e:
        jobs[job_id] = {"status": "error", "message": str(e)}


@api.post("/apps/{app_id}/run")
def run_app(app_id: int, dry_run: bool = True):
    a = get_app(app_id)
    if not a:
        return {"error": "App not found"}
    if not a.get("active"):
        return {"error": "App inactive"}
    if not a.get("management_key") or not a.get("gam_publisher_id"):
        return {"error": "App'in publisher'inda management_key veya gam_publisher_id eksik"}

    # Aynı app için çalışan job var mı?
    for jid, j in jobs.items():
        if j.get("app_id") == app_id and j.get("status") == "running":
            return {"error": "Bu app icin zaten bir job calisiyor", "job_id": jid}

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "app_id": app_id, "dry_run": dry_run}

    thread = threading.Thread(target=_run_sync, args=(job_id, a, dry_run), daemon=True)
    thread.start()

    return {"status": "started", "job_id": job_id}


@api.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}
    return job


# === Approvals (Hybrid Mode) ===

@api.get("/approvals")
def list_approvals():
    return get_pending_approvals()


@api.get("/approvals/{job_id}")
def get_approval_detail(job_id: str):
    approval = get_approval(job_id)
    if not approval:
        return {"error": "Approval not found"}

    # İlgili dry run loglarını ekle
    logs = get_job_logs(run_job_id=job_id, limit=500)
    approval["logs"] = logs
    return approval


@api.post("/approvals/{job_id}/confirm")
def confirm_approval(job_id: str):
    approval = get_approval(job_id)
    if not approval:
        return {"error": "Approval not found"}
    if approval["status"] != "pending":
        return {"error": f"Approval zaten {approval['status']}"}

    # Expire kontrolü
    if approval["expires_at"]:
        expires = datetime.fromisoformat(approval["expires_at"]) if isinstance(approval["expires_at"], str) else approval["expires_at"]
        if expires < datetime.utcnow():
            return {"error": "Approval suresi dolmus (48 saat)"}

    approve_job(job_id)

    a = get_app(approval["app_id"])
    if not a:
        return {"error": "App not found"}

    run_job_id = str(uuid.uuid4())[:8]
    jobs[run_job_id] = {"status": "running", "app_id": a["id"], "dry_run": False}

    thread = threading.Thread(target=_run_sync, args=(run_job_id, a, False), daemon=True)
    thread.start()

    return {"status": "approved", "run_job_id": run_job_id}


# === Snapshots / Rollback ===

@api.get("/snapshots")
def list_snapshots(app_id: Optional[int] = None, run_job_id: Optional[str] = None,
                   status: Optional[str] = None):
    return get_snapshots(app_id=app_id, run_job_id=run_job_id, status=status)


@api.post("/snapshots/{snapshot_id}/rollback")
def rollback(snapshot_id: int):
    snap = get_snapshot(snapshot_id)
    if not snap:
        return {"error": "Snapshot not found"}
    if snap["status"] == "rolled_back":
        return {"error": "Bu snapshot zaten rollback edilmis"}

    a = get_app(snap["app_id"])
    if not a:
        return {"error": "App not found"}

    ok, err = rollback_snapshot(snap, a["management_key"])
    if ok:
        mark_snapshot_rolled_back(snapshot_id)
        log_operation(
            publisher_id=a.get("publisher_id"),
            publisher_name=a.get("publisher_name", ""),
            app_id=a["id"], app_label=a["label"],
            run_job_id=snap.get("run_job_id", ""),
            ad_unit_id=snap["max_ad_unit_id"],
            old_value=snap["network_ad_unit_id_new"],
            new_value=snap["network_ad_unit_id_old"],
            status="ROLLED_BACK",
        )
        return {"status": "rolled_back"}
    return {"error": f"Rollback basarisiz: {err}"}


# === Logs ===

@api.get("/logs")
def list_logs(app_id: Optional[int] = None, publisher_id: Optional[int] = None,
              run_job_id: Optional[str] = None, limit: int = 200):
    return get_job_logs(
        publisher_id=publisher_id, app_id=app_id,
        run_job_id=run_job_id, limit=limit,
    )


# --- Router'ı ekle ---
app.include_router(api)


# --- React build serve ---
BUILD_DIR = Path(__file__).parent / "build"

if BUILD_DIR.exists():
    app.mount("/static", StaticFiles(directory=BUILD_DIR / "static"), name="static")

    @app.get("/{full_path:path}")
    async def serve_react(full_path: str):
        """API dışındaki tüm route'ları React'e yönlendir."""
        file_path = BUILD_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(BUILD_DIR / "index.html")
