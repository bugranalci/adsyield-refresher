import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", "adsyield.db")

def get_conn():
    """Thread-safe connection al, foreign key enforcement aç"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Veritabanını ve tabloları oluştur"""
    conn = get_conn()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS publishers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            management_key  TEXT NOT NULL,
            publisher_tag   TEXT NOT NULL,
            find_string     TEXT NOT NULL,
            replace_string  TEXT NOT NULL,
            frequency_days  INTEGER DEFAULT 2,
            mode            TEXT DEFAULT 'manual',
            notify_email    TEXT DEFAULT '',
            current_version INTEGER DEFAULT 1,
            active          INTEGER DEFAULT 1,
            last_run        TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS job_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            publisher_id    INTEGER,
            publisher_name  TEXT,
            ad_unit_id      TEXT,
            ad_unit_name    TEXT,
            old_value       TEXT,
            new_value       TEXT,
            status          TEXT,
            error_message   TEXT,
            ran_at          TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (publisher_id) REFERENCES publishers(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS pending_approvals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            publisher_id    INTEGER NOT NULL,
            job_id          TEXT NOT NULL UNIQUE,
            matched         INTEGER DEFAULT 0,
            skipped         INTEGER DEFAULT 0,
            dry_run_data    TEXT,
            status          TEXT DEFAULT 'pending',
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at      TEXT,
            approved_at     TEXT,
            FOREIGN KEY (publisher_id) REFERENCES publishers(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("[DB] Veritabanı hazır")

# --- Publisher CRUD ---

def add_publisher(name, management_key, publisher_tag, find_string, replace_string,
                  frequency_days=2, mode='manual', notify_email=''):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO publishers
        (name, management_key, publisher_tag, find_string, replace_string, frequency_days, mode, notify_email)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, management_key, publisher_tag, find_string, replace_string, frequency_days, mode, notify_email))
    conn.commit()
    publisher_id = c.lastrowid
    conn.close()
    print(f"[DB] Publisher eklendi: {name} (id={publisher_id})")
    return publisher_id

def get_active_publishers():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM publishers WHERE active = 1")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_publishers():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM publishers ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_publisher(publisher_id, find_string, replace_string, frequency_days, active,
                     mode=None, notify_email=None):
    conn = get_conn()
    c = conn.cursor()
    fields = "find_string = ?, replace_string = ?, frequency_days = ?, active = ?"
    params = [find_string, replace_string, frequency_days, active]
    if mode is not None:
        fields += ", mode = ?"
        params.append(mode)
    if notify_email is not None:
        fields += ", notify_email = ?"
        params.append(notify_email)
    params.append(publisher_id)
    c.execute(f"UPDATE publishers SET {fields} WHERE id = ?", params)
    updated = c.rowcount
    conn.commit()
    conn.close()
    return updated > 0

def delete_publisher(publisher_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM pending_approvals WHERE publisher_id = ?", (publisher_id,))
    c.execute("DELETE FROM job_logs WHERE publisher_id = ?", (publisher_id,))
    c.execute("DELETE FROM publishers WHERE id = ?", (publisher_id,))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    return deleted > 0

def update_last_run(publisher_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE publishers SET last_run = ? WHERE id = ?",
        (datetime.now().isoformat(), publisher_id)
    )
    conn.commit()
    conn.close()

# --- Job Logs ---

def log_operation(publisher_id, publisher_name, ad_unit_id, ad_unit_name, old_value, new_value, status, error_message=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO job_logs
        (publisher_id, publisher_name, ad_unit_id, ad_unit_name, old_value, new_value, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (publisher_id, publisher_name, ad_unit_id, ad_unit_name, old_value, new_value, status, error_message))
    conn.commit()
    conn.close()

def get_job_logs(publisher_id=None, limit=100):
    conn = get_conn()
    c = conn.cursor()
    if publisher_id:
        c.execute(
            "SELECT * FROM job_logs WHERE publisher_id = ? ORDER BY ran_at DESC LIMIT ?",
            (publisher_id, limit)
        )
    else:
        c.execute("SELECT * FROM job_logs ORDER BY ran_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- Pending Approvals ---

def create_approval(publisher_id, job_id, matched, skipped, dry_run_data=""):
    conn = get_conn()
    c = conn.cursor()
    expires = (datetime.now() + timedelta(hours=48)).isoformat()
    c.execute('''
        INSERT INTO pending_approvals
        (publisher_id, job_id, matched, skipped, dry_run_data, status, expires_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
    ''', (publisher_id, job_id, matched, skipped, dry_run_data, expires))
    conn.commit()
    conn.close()

def get_approval(job_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM pending_approvals WHERE job_id = ?", (job_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_pending_approvals():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        SELECT pa.*, p.name as publisher_name, p.find_string, p.replace_string
        FROM pending_approvals pa
        JOIN publishers p ON pa.publisher_id = p.id
        WHERE pa.status = 'pending'
        ORDER BY pa.created_at DESC
    ''')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def approve_job(job_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        UPDATE pending_approvals
        SET status = 'approved', approved_at = ?
        WHERE job_id = ? AND status = 'pending'
    ''', (datetime.now().isoformat(), job_id))
    updated = c.rowcount
    conn.commit()
    conn.close()
    return updated > 0

def expire_old_approvals():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        UPDATE pending_approvals
        SET status = 'expired'
        WHERE status = 'pending' AND expires_at < ?
    ''', (datetime.now().isoformat(),))
    expired = c.rowcount
    conn.commit()
    conn.close()
    return expired

def get_hybrid_publishers_due():
    """Hybrid modda olup çalışma zamanı gelen publisher'ları getir"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        SELECT * FROM publishers
        WHERE active = 1 AND mode = 'hybrid'
    ''')
    rows = c.fetchall()
    conn.close()

    now = datetime.now()
    due = []
    for row in rows:
        p = dict(row)
        if not p["last_run"]:
            due.append(p)
            continue
        last = datetime.fromisoformat(p["last_run"])
        if (now - last).days >= p["frequency_days"]:
            due.append(p)
    return due

if __name__ == "__main__":
    init_db()

    # Test publisher — key'ler referans olarak saklanıyor
    # add_publisher(
    #     name           = "TheGameOps Test",
    #     management_key = "e0757bd737fa69c9d7c8dea73f3e4d57bc403d2a557073180b8e3a938d773465e7759b6c89fb89297e66d2",
    #     publisher_tag  = "thegameops",
    #     find_string    = "_0_",
    #     replace_string = "_TEST_",
    #     frequency_days = 2
    # )

    publishers = get_all_publishers()
    for p in publishers:
        print(f"  - {p['name']} | tag: {p['publisher_tag']} | find: {p['find_string']}")
