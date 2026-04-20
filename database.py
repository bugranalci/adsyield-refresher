"""Veritabanı CRUD fonksiyonları — SQLAlchemy tabanlı.

db.py'deki modelleri kullanır. Eski sqlite3 tabanlı API ile uyumlu
fonksiyon isimleri korundu ki api.py ve engine.py minimum değişiklikle çalışabilsin.
"""
from datetime import datetime, timedelta
from sqlalchemy import select, delete, update, and_
from db import (
    init_db as _init_db,
    get_session,
    Publisher, App, SlotCache, Snapshot, JobLog, PendingApproval,
)


def init_db():
    _init_db()


def _to_dict(obj):
    """SQLAlchemy objesi → dict"""
    if obj is None:
        return None
    from decimal import Decimal
    result = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        elif isinstance(val, Decimal):
            val = float(val)
        result[col.name] = val
    return result


# --- Publisher CRUD ---

def add_publisher(name, management_key, gam_publisher_id, publisher_tag=None,
                  find_string=None, replace_string=None,
                  frequency_days=2, mode="manual", notify_email=""):
    """Yeni publisher ekle.

    Not: publisher_tag/find_string/replace_string eski API uyumluluğu için kabul edilir
    ama yeni sistemde kullanılmaz, ignore edilir.
    """
    with get_session() as s:
        p = Publisher(
            name=name,
            management_key=management_key,
            gam_publisher_id=gam_publisher_id or "",
            frequency_days=frequency_days,
            mode=mode,
            notify_email=notify_email,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        print(f"[DB] Publisher eklendi: {name} (id={p.id})")
        return p.id


def get_all_publishers():
    with get_session() as s:
        rows = s.execute(select(Publisher).order_by(Publisher.id)).scalars().all()
        return [_to_dict(r) for r in rows]


def get_active_publishers():
    with get_session() as s:
        rows = s.execute(select(Publisher).where(Publisher.active == 1)).scalars().all()
        return [_to_dict(r) for r in rows]


def get_publisher(publisher_id):
    with get_session() as s:
        p = s.get(Publisher, publisher_id)
        return _to_dict(p)


def update_publisher(publisher_id, active=None, frequency_days=None,
                     mode=None, notify_email=None, gam_publisher_id=None,
                     # eski API uyumluluğu
                     find_string=None, replace_string=None):
    with get_session() as s:
        p = s.get(Publisher, publisher_id)
        if not p:
            return False
        if active is not None:
            p.active = active
        if frequency_days is not None:
            p.frequency_days = frequency_days
        if mode is not None:
            p.mode = mode
        if notify_email is not None:
            p.notify_email = notify_email
        if gam_publisher_id is not None:
            p.gam_publisher_id = gam_publisher_id
        s.commit()
        return True


def delete_publisher(publisher_id):
    with get_session() as s:
        p = s.get(Publisher, publisher_id)
        if not p:
            return False
        s.delete(p)  # cascade ile apps, snapshots, slot_cache da silinir
        s.commit()
        return True


def update_last_run(publisher_id):
    with get_session() as s:
        p = s.get(Publisher, publisher_id)
        if p:
            p.last_run = datetime.utcnow()
            s.commit()


# --- App CRUD ---

def add_app(publisher_id, label, gam_app_name, platform):
    with get_session() as s:
        a = App(
            publisher_id=publisher_id,
            label=label,
            gam_app_name=gam_app_name,
            platform=platform,
        )
        s.add(a)
        s.commit()
        s.refresh(a)
        print(f"[DB] App eklendi: {label} (id={a.id})")
        return a.id


def get_apps_by_publisher(publisher_id):
    with get_session() as s:
        rows = s.execute(
            select(App).where(App.publisher_id == publisher_id).order_by(App.id)
        ).scalars().all()
        return [_to_dict(r) for r in rows]


def get_app(app_id):
    with get_session() as s:
        a = s.get(App, app_id)
        if not a:
            return None
        d = _to_dict(a)
        # Publisher bilgisini de ekle (joined)
        if a.publisher:
            d["publisher_name"] = a.publisher.name
            d["gam_publisher_id"] = a.publisher.gam_publisher_id
            d["management_key"] = a.publisher.management_key
        return d


def update_app(app_id, label=None, gam_app_name=None, platform=None, active=None):
    with get_session() as s:
        a = s.get(App, app_id)
        if not a:
            return False
        if label is not None:
            a.label = label
        if gam_app_name is not None:
            a.gam_app_name = gam_app_name
        if platform is not None:
            a.platform = platform
        if active is not None:
            a.active = active
        s.commit()
        return True


def delete_app(app_id):
    with get_session() as s:
        a = s.get(App, app_id)
        if not a:
            return False
        s.delete(a)
        s.commit()
        return True


def update_app_last_run(app_id):
    with get_session() as s:
        a = s.get(App, app_id)
        if a:
            a.last_run = datetime.utcnow()
            s.commit()


# --- Slot Cache ---

def upsert_slot_cache(app_id, format_, platform, cpm, max_version):
    """Slot varsa update, yoksa insert."""
    with get_session() as s:
        existing = s.execute(
            select(SlotCache).where(and_(
                SlotCache.app_id == app_id,
                SlotCache.format == format_,
                SlotCache.platform == platform,
                SlotCache.cpm == cpm,
            ))
        ).scalar_one_or_none()
        if existing:
            existing.max_version = max_version
            existing.synced_at = datetime.utcnow()
        else:
            s.add(SlotCache(
                app_id=app_id, format=format_, platform=platform,
                cpm=cpm, max_version=max_version,
            ))
        s.commit()


def get_slot_cache(app_id):
    with get_session() as s:
        rows = s.execute(
            select(SlotCache).where(SlotCache.app_id == app_id)
        ).scalars().all()
        return [_to_dict(r) for r in rows]


def clear_slot_cache(app_id):
    with get_session() as s:
        s.execute(delete(SlotCache).where(SlotCache.app_id == app_id))
        s.commit()


# --- Snapshot ---

def create_snapshot(app_id, run_job_id, max_ad_unit_id, max_ad_unit_name,
                    old_id, new_id, full_config=None):
    with get_session() as s:
        snap = Snapshot(
            app_id=app_id,
            run_job_id=run_job_id,
            max_ad_unit_id=max_ad_unit_id,
            max_ad_unit_name=max_ad_unit_name or "",
            network_ad_unit_id_old=old_id,
            network_ad_unit_id_new=new_id,
            full_config=full_config,
        )
        s.add(snap)
        s.commit()
        s.refresh(snap)
        return snap.id


def get_snapshots(app_id=None, run_job_id=None, status=None):
    with get_session() as s:
        q = select(Snapshot)
        if app_id is not None:
            q = q.where(Snapshot.app_id == app_id)
        if run_job_id is not None:
            q = q.where(Snapshot.run_job_id == run_job_id)
        if status is not None:
            q = q.where(Snapshot.status == status)
        q = q.order_by(Snapshot.created_at.desc())
        rows = s.execute(q).scalars().all()
        return [_to_dict(r) for r in rows]


def get_snapshot(snapshot_id):
    with get_session() as s:
        snap = s.get(Snapshot, snapshot_id)
        return _to_dict(snap)


def mark_snapshot_rolled_back(snapshot_id):
    with get_session() as s:
        snap = s.get(Snapshot, snapshot_id)
        if not snap:
            return False
        snap.status = "rolled_back"
        snap.rolled_back_at = datetime.utcnow()
        s.commit()
        return True


def cleanup_old_snapshots(days=30):
    """30 günden eski snapshot'ları sil."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    with get_session() as s:
        result = s.execute(
            delete(Snapshot).where(Snapshot.created_at < cutoff)
        )
        s.commit()
        return result.rowcount


# --- Job Logs ---

def log_operation(publisher_id=None, publisher_name="", app_id=None, app_label="",
                  run_job_id="", ad_unit_id="", ad_unit_name="",
                  old_value="", new_value="", status="", error_message=""):
    with get_session() as s:
        log = JobLog(
            publisher_id=publisher_id,
            publisher_name=publisher_name,
            app_id=app_id,
            app_label=app_label,
            run_job_id=run_job_id,
            ad_unit_id=ad_unit_id,
            ad_unit_name=ad_unit_name,
            old_value=old_value,
            new_value=new_value,
            status=status,
            error_message=error_message,
        )
        s.add(log)
        s.commit()


def get_job_logs(publisher_id=None, app_id=None, run_job_id=None, limit=200):
    with get_session() as s:
        q = select(JobLog)
        if publisher_id is not None:
            q = q.where(JobLog.publisher_id == publisher_id)
        if app_id is not None:
            q = q.where(JobLog.app_id == app_id)
        if run_job_id is not None:
            q = q.where(JobLog.run_job_id == run_job_id)
        q = q.order_by(JobLog.ran_at.desc()).limit(limit)
        rows = s.execute(q).scalars().all()
        return [_to_dict(r) for r in rows]


# --- Pending Approvals ---

def create_approval(app_id, job_id, matched, skipped, expire_hours=48):
    with get_session() as s:
        approval = PendingApproval(
            app_id=app_id,
            job_id=job_id,
            matched=matched,
            skipped=skipped,
            expires_at=datetime.utcnow() + timedelta(hours=expire_hours),
        )
        s.add(approval)
        s.commit()


def get_approval(job_id):
    with get_session() as s:
        a = s.execute(
            select(PendingApproval).where(PendingApproval.job_id == job_id)
        ).scalar_one_or_none()
        return _to_dict(a)


def get_pending_approvals():
    with get_session() as s:
        rows = s.execute(
            select(PendingApproval)
            .where(PendingApproval.status == "pending")
            .order_by(PendingApproval.created_at.desc())
        ).scalars().all()

        result = []
        for a in rows:
            d = _to_dict(a)
            # App + Publisher bilgisini ekle
            if a.app_id:
                app_row = s.get(App, a.app_id)
                if app_row:
                    d["app_label"] = app_row.label
                    d["app_platform"] = app_row.platform
                    if app_row.publisher:
                        d["publisher_name"] = app_row.publisher.name
            result.append(d)
        return result


def approve_job(job_id):
    with get_session() as s:
        a = s.execute(
            select(PendingApproval).where(
                and_(PendingApproval.job_id == job_id,
                     PendingApproval.status == "pending")
            )
        ).scalar_one_or_none()
        if not a:
            return False
        a.status = "approved"
        a.approved_at = datetime.utcnow()
        s.commit()
        return True


def expire_old_approvals():
    with get_session() as s:
        result = s.execute(
            update(PendingApproval)
            .where(and_(
                PendingApproval.status == "pending",
                PendingApproval.expires_at < datetime.utcnow()
            ))
            .values(status="expired")
        )
        s.commit()
        return result.rowcount


# --- Hybrid Scheduler ---

def get_hybrid_publishers_due():
    """Hybrid modda olup çalışma zamanı gelen publisher'ları getir."""
    with get_session() as s:
        rows = s.execute(
            select(Publisher).where(and_(
                Publisher.active == 1,
                Publisher.mode == "hybrid",
            ))
        ).scalars().all()

        now = datetime.utcnow()
        due = []
        for p in rows:
            if not p.last_run:
                due.append(_to_dict(p))
                continue
            if (now - p.last_run).days >= p.frequency_days:
                due.append(_to_dict(p))
        return due


if __name__ == "__main__":
    init_db()
    print("Publishers:", get_all_publishers())
