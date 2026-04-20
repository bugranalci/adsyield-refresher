"""Arka plan scheduler'ı.

Cron job'ları:
  - Her gün 03:00: Hybrid app'lerin slot cache'ini yenile + dry run + email
  - Her gün 03:30: 30+ gün eski snapshot'ları sil
  - Her saat: expired approval'ları işaretle

Basit implementasyon — time.sleep + saat kontrolü.
apscheduler gibi ağır bir paket kullanmadık, çünkü Railway'de tek instance çalışıyor.
"""
import time
import uuid
import threading
from datetime import datetime

from database import (
    get_active_publishers, get_apps_by_publisher, get_app,
    expire_old_approvals, create_approval, cleanup_old_snapshots,
)
from engine import sync_app
from mailer import send_dry_run_report

# --- Ayarlar ---
SCHEDULER_CHECK_INTERVAL_SECONDS = 300  # 5 dakikada bir kontrol
DAILY_SYNC_HOUR = 3                      # 03:00'da hybrid sync
SNAPSHOT_CLEANUP_HOUR = 3                # 03:30'da cleanup (slot sync'ten sonra)
SNAPSHOT_CLEANUP_MINUTE = 30
SNAPSHOT_RETENTION_DAYS = 30

# State — hangi günler hangi job'lar çalıştı takibi
_last_run = {
    "hybrid_sync": None,
    "snapshot_cleanup": None,
    "approval_expire": None,
}


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SCHED] {msg}")


def _today():
    return datetime.now().strftime("%Y-%m-%d")


# --- Hybrid Sync ---

def run_hybrid_sync():
    """Her hybrid publisher'ın her aktif app'i için dry run çalıştır, email gönder."""
    publishers = [p for p in get_active_publishers() if p.get("mode") == "hybrid"]
    if not publishers:
        _log("Hybrid publisher yok")
        return

    _log(f"{len(publishers)} hybrid publisher islenecek")

    for pub in publishers:
        if not pub.get("notify_email"):
            _log(f"  {pub['name']} — notify_email bos, atlaniyor")
            continue

        apps = get_apps_by_publisher(pub["id"])
        active_apps = [a for a in apps if a.get("active")]
        if not active_apps:
            _log(f"  {pub['name']} — aktif app yok")
            continue

        for app_row in active_apps:
            # App'i publisher bilgisiyle zenginleştir
            app_detail = get_app(app_row["id"])
            if not app_detail:
                continue

            job_id = str(uuid.uuid4())[:8]
            _log(f"  {app_detail['label']} — dry run (job: {job_id})")

            try:
                result = sync_app(app_detail, run_job_id=job_id, dry_run=True)
                matched = result.get("matched", 0)

                if matched == 0:
                    _log(f"    {app_detail['label']} — eslesme yok, email gonderilmiyor")
                    continue

                create_approval(
                    app_id=app_detail["id"],
                    job_id=job_id,
                    matched=matched,
                    skipped=result.get("skipped", 0),
                )

                send_dry_run_report(
                    to_email=pub["notify_email"],
                    publisher_name=f"{pub['name']} — {app_detail['label']}",
                    find_string="(GAM slot degisiklikleri)",
                    replace_string=f"{matched} entry guncellenecek",
                    matched=matched,
                    skipped=result.get("skipped", 0),
                    total_units=matched + result.get("skipped", 0),
                    job_id=job_id,
                )

                _log(f"    {app_detail['label']} — email gonderildi ({matched} eslesme)")

            except Exception as e:
                _log(f"    {app_detail['label']} — HATA: {e}")


# --- Scheduler Loop ---

def _should_run_hybrid_sync() -> bool:
    now = datetime.now()
    today = _today()
    return (
        now.hour == DAILY_SYNC_HOUR
        and _last_run["hybrid_sync"] != today
    )


def _should_run_snapshot_cleanup() -> bool:
    now = datetime.now()
    today = _today()
    return (
        now.hour == SNAPSHOT_CLEANUP_HOUR
        and now.minute >= SNAPSHOT_CLEANUP_MINUTE
        and _last_run["snapshot_cleanup"] != today
    )


def _should_run_approval_expire() -> bool:
    """Her saat başı expired approval'ları işaretle."""
    now = datetime.now()
    current_hour = now.strftime("%Y-%m-%d %H")
    return _last_run["approval_expire"] != current_hour


def scheduler_tick():
    """Her tick'te kontrol edilen job'lar."""
    try:
        if _should_run_hybrid_sync():
            _log("Hybrid sync baslatiliyor...")
            run_hybrid_sync()
            _last_run["hybrid_sync"] = _today()

        if _should_run_snapshot_cleanup():
            deleted = cleanup_old_snapshots(days=SNAPSHOT_RETENTION_DAYS)
            _log(f"Snapshot cleanup: {deleted} kayit silindi (30+ gun)")
            _last_run["snapshot_cleanup"] = _today()

        if _should_run_approval_expire():
            expired = expire_old_approvals()
            if expired:
                _log(f"{expired} approval expire edildi")
            _last_run["approval_expire"] = datetime.now().strftime("%Y-%m-%d %H")
    except Exception as e:
        _log(f"HATA: {e}")


def scheduler_loop():
    _log("Scheduler baslatildi (hybrid sync: her gun 03:00)")
    while True:
        scheduler_tick()
        time.sleep(SCHEDULER_CHECK_INTERVAL_SECONDS)


def start_scheduler():
    """Scheduler'ı background thread olarak başlat."""
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    _log("Background thread olarak calisiyor")
    return thread
