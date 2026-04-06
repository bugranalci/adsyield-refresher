import os
import threading
import uuid
from pathlib import Path
from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from database import (
    init_db, get_all_publishers, add_publisher, get_job_logs,
    update_publisher as db_update_publisher,
    delete_publisher as db_delete_publisher,
    get_approval, approve_job, get_pending_approvals,
)
from engine import run_refresh
from scheduler import start_scheduler

app = FastAPI()

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
start_scheduler()

# In-memory job tracker
jobs = {}

def mask_key(key):
    if len(key) <= 6:
        return "***"
    return "***" + key[-6:]

# --- API Router (tüm endpoint'ler /api/ altında) ---

api = APIRouter(prefix="/api")

class PublisherCreate(BaseModel):
    name: str
    management_key: str
    publisher_tag: str
    find_string: str
    replace_string: str
    frequency_days: int = 2
    mode: str = "manual"
    notify_email: str = ""

class PublisherUpdate(BaseModel):
    find_string: str
    replace_string: str
    frequency_days: int
    active: int
    mode: Optional[str] = None
    notify_email: Optional[str] = None

@api.get("/publishers")
def list_publishers():
    publishers = get_all_publishers()
    for p in publishers:
        p["management_key"] = mask_key(p["management_key"])
    return publishers

@api.post("/publishers")
def create_publisher(p: PublisherCreate):
    publisher_id = add_publisher(
        p.name, p.management_key, p.publisher_tag,
        p.find_string, p.replace_string, p.frequency_days,
        p.mode, p.notify_email
    )
    return {"id": publisher_id, "status": "created"}

@api.put("/publishers/{publisher_id}")
def update_publisher(publisher_id: int, p: PublisherUpdate):
    found = db_update_publisher(
        publisher_id, p.find_string, p.replace_string,
        p.frequency_days, p.active, p.mode, p.notify_email
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

# --- Run ---

def _run_job(job_id, publisher, dry_run):
    try:
        success, failed, skipped, matched = run_refresh(publisher, dry_run=dry_run)
        jobs[job_id] = {
            "status": "no_match" if matched == 0 else "done",
            "message": f"Eslesme bulunamadi. Find string'i kontrol et: {publisher['find_string']}" if matched == 0 else None,
            "success": matched if dry_run else success,
            "failed": failed,
            "skipped": skipped,
            "matched": matched,
            "dry_run": dry_run,
        }
    except Exception as e:
        jobs[job_id] = {"status": "error", "message": str(e)}

@api.post("/publishers/{publisher_id}/run")
def run_publisher(publisher_id: int, dry_run: bool = True):
    publishers = get_all_publishers()
    publisher = next((p for p in publishers if p["id"] == publisher_id), None)
    if not publisher:
        return {"error": "Publisher not found"}

    if not publisher["active"]:
        return {"error": "Publisher inactive — once aktif et"}

    for jid, job in jobs.items():
        if job.get("publisher_id") == publisher_id and job.get("status") == "running":
            return {"error": "Bu publisher icin zaten bir job calisiyor", "job_id": jid}

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "publisher_id": publisher_id, "dry_run": dry_run}

    thread = threading.Thread(target=_run_job, args=(job_id, publisher, dry_run), daemon=True)
    thread.start()

    return {"status": "started", "job_id": job_id}

@api.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}
    return job

# --- Approvals ---

@api.get("/approvals")
def list_approvals():
    return get_pending_approvals()

@api.get("/approvals/{job_id}")
def get_approval_detail(job_id: str):
    approval = get_approval(job_id)
    if not approval:
        return {"error": "Approval not found"}

    publishers = get_all_publishers()
    publisher = next((p for p in publishers if p["id"] == approval["publisher_id"]), None)
    if publisher:
        approval["publisher_name"] = publisher["name"]
        approval["find_string"] = publisher["find_string"]
        approval["replace_string"] = publisher["replace_string"]

    logs = get_job_logs(publisher_id=approval["publisher_id"], limit=500)
    dry_logs = [l for l in logs if l["status"] == "DRY_RUN"]
    approval["logs"] = dry_logs[:approval["matched"]]

    return approval

@api.post("/approvals/{job_id}/confirm")
def confirm_approval(job_id: str):
    approval = get_approval(job_id)
    if not approval:
        return {"error": "Approval not found"}
    if approval["status"] != "pending":
        return {"error": f"Approval zaten {approval['status']}"}

    from datetime import datetime
    if approval["expires_at"] and datetime.fromisoformat(approval["expires_at"]) < datetime.now():
        return {"error": "Approval suresi dolmus (48 saat)"}

    approve_job(job_id)

    publishers = get_all_publishers()
    publisher = next((p for p in publishers if p["id"] == approval["publisher_id"]), None)
    if not publisher:
        return {"error": "Publisher not found"}

    run_job_id = str(uuid.uuid4())[:8]
    jobs[run_job_id] = {"status": "running", "publisher_id": publisher["id"], "dry_run": False}

    thread = threading.Thread(target=_run_job, args=(run_job_id, publisher, False), daemon=True)
    thread.start()

    return {"status": "approved", "run_job_id": run_job_id}

@api.get("/logs")
def list_logs():
    return get_job_logs(limit=200)

# --- Router'ı ekle ---
app.include_router(api)

# --- React build serve ---
BUILD_DIR = Path(__file__).parent / "build"

if BUILD_DIR.exists():
    app.mount("/static", StaticFiles(directory=BUILD_DIR / "static"), name="static")

    @app.get("/{full_path:path}")
    async def serve_react(full_path: str):
        """API dışındaki tüm route'ları React'e yönlendir"""
        file_path = BUILD_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(BUILD_DIR / "index.html")
