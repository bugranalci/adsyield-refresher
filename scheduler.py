import time
import uuid
import threading
from datetime import datetime
from database import (
    get_hybrid_publishers_due, expire_old_approvals, create_approval
)
from engine import run_refresh
from mailer import send_dry_run_report

CHECK_INTERVAL = 3600  # Her saat kontrol et

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SCHEDULER] {msg}")

def run_hybrid_check():
    """Hybrid modda zamanı gelen publisher'lar için dry run çalıştır ve email gönder"""
    expired = expire_old_approvals()
    if expired:
        log(f"{expired} eski onay expire edildi")

    due_publishers = get_hybrid_publishers_due()
    if not due_publishers:
        log("Zamani gelen hybrid publisher yok")
        return

    log(f"{len(due_publishers)} hybrid publisher zamani gelmis")

    for publisher in due_publishers:
        if not publisher.get("notify_email"):
            log(f"  {publisher['name']} — notify_email bos, atlaniyor")
            continue

        job_id = str(uuid.uuid4())[:8]
        log(f"  {publisher['name']} — dry run baslatiliyor (job: {job_id})")

        try:
            success, failed, skipped, matched = run_refresh(publisher, dry_run=True)

            if matched == 0:
                log(f"  {publisher['name']} — eslesme yok, email gonderilmiyor")
                continue

            create_approval(
                publisher_id=publisher["id"],
                job_id=job_id,
                matched=matched,
                skipped=skipped
            )

            send_dry_run_report(
                to_email=publisher["notify_email"],
                publisher_name=publisher["name"],
                find_string=publisher["find_string"],
                replace_string=publisher["replace_string"],
                matched=matched,
                skipped=skipped,
                total_units=matched + skipped,
                job_id=job_id
            )

            log(f"  {publisher['name']} — {matched} eslesme, email gonderildi")

        except Exception as e:
            log(f"  {publisher['name']} — HATA: {e}")

def scheduler_loop():
    """Ana scheduler döngüsü"""
    log("Scheduler baslatildi")
    while True:
        try:
            run_hybrid_check()
        except Exception as e:
            log(f"HATA: {e}")
        time.sleep(CHECK_INTERVAL)

def start_scheduler():
    """Scheduler'ı background thread olarak başlat"""
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    log("Background thread olarak calisiyor")
    return thread
