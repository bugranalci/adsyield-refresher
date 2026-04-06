import os
import threading
import uuid
from fastapi import FastAPI
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

# Scheduler'ı başlat (hybrid publisher'lar için)
start_scheduler()

# In-memory job tracker
jobs = {}

def mask_key(key):
    if len(key) <= 6:
        return "***"
    return "***" + key[-6:]

# --- Pydantic Models ---

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

# --- Publisher Endpoints ---

@app.get("/publishers")
def list_publishers():
    publishers = get_all_publishers()
    for p in publishers:
        p["management_key"] = mask_key(p["management_key"])
    return publishers

@app.post("/publishers")
def create_publisher(p: PublisherCreate):
    publisher_id = add_publisher(
        p.name, p.management_key, p.publisher_tag,
        p.find_string, p.replace_string, p.frequency_days,
        p.mode, p.notify_email
    )
    return {"id": publisher_id, "status": "created"}

@app.put("/publishers/{publisher_id}")
def update_publisher(publisher_id: int, p: PublisherUpdate):
    found = db_update_publisher(
        publisher_id, p.find_string, p.replace_string,
        p.frequency_days, p.active, p.mode, p.notify_email
    )
    if not found:
        return {"error": "Publisher not found"}
    return {"status": "updated"}

@app.delete("/publishers/{publisher_id}")
def delete_publisher(publisher_id: int):
    found = db_delete_publisher(publisher_id)
    if not found:
        return {"error": "Publisher not found"}
    return {"status": "deleted"}

# --- Run Endpoints ---

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

@app.post("/publishers/{publisher_id}/run")
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

@app.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}
    return job

# --- Approval Endpoints ---

@app.get("/approvals")
def list_approvals():
    return get_pending_approvals()

@app.get("/approvals/{job_id}")
def get_approval_detail(job_id: str):
    approval = get_approval(job_id)
    if not approval:
        return {"error": "Approval not found"}

    # Publisher bilgilerini ekle
    publishers = get_all_publishers()
    publisher = next((p for p in publishers if p["id"] == approval["publisher_id"]), None)
    if publisher:
        approval["publisher_name"] = publisher["name"]
        approval["find_string"] = publisher["find_string"]
        approval["replace_string"] = publisher["replace_string"]

    # İlgili dry run loglarını çek
    logs = get_job_logs(publisher_id=approval["publisher_id"], limit=500)
    dry_logs = [l for l in logs if l["status"] == "DRY_RUN"]
    approval["logs"] = dry_logs[:approval["matched"]]

    return approval

@app.post("/approvals/{job_id}/confirm")
def confirm_approval(job_id: str):
    approval = get_approval(job_id)
    if not approval:
        return {"error": "Approval not found"}
    if approval["status"] != "pending":
        return {"error": f"Approval zaten {approval['status']}"}

    # Expire kontrolü
    from datetime import datetime
    if approval["expires_at"] and datetime.fromisoformat(approval["expires_at"]) < datetime.now():
        return {"error": "Approval suresi dolmus (48 saat)"}

    # Onayla
    approve_job(job_id)

    # Publisher'ı bul ve canlı run başlat
    publishers = get_all_publishers()
    publisher = next((p for p in publishers if p["id"] == approval["publisher_id"]), None)
    if not publisher:
        return {"error": "Publisher not found"}

    run_job_id = str(uuid.uuid4())[:8]
    jobs[run_job_id] = {"status": "running", "publisher_id": publisher["id"], "dry_run": False}

    thread = threading.Thread(target=_run_job, args=(run_job_id, publisher, False), daemon=True)
    thread.start()

    return {"status": "approved", "run_job_id": run_job_id}

# --- Logs ---

@app.get("/logs")
def list_logs():
    return get_job_logs(limit=200)
