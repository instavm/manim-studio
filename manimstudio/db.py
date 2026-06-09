"""SQLite job persistence. Thread-safe via short-lived connections."""
import sqlite3, json, time, os, threading
from contextlib import contextmanager

DB_PATH = os.environ.get("MS_DB_PATH", "/app/manimstudio/jobs.db")
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    ip           TEXT NOT NULL,
    prompt       TEXT NOT NULL,
    status       TEXT NOT NULL,        -- queued|drafting|rendering|done|failed
    attempt      INTEGER NOT NULL DEFAULT 0,
    log          TEXT NOT NULL DEFAULT '',
    video_path   TEXT,
    error        TEXT,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_created ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS jobs_ip      ON jobs(ip, created_at);
"""

def init():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with conn() as c:
        c.executescript(SCHEMA)

@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    try:
        yield c
    finally:
        c.close()

def create_job(job_id: str, ip: str, prompt: str):
    now = time.time()
    with _lock, conn() as c:
        c.execute(
            "INSERT INTO jobs(id, ip, prompt, status, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?)",
            (job_id, ip, prompt, "queued", now, now),
        )

def update_job(job_id: str, **fields):
    if not fields:
        return
    fields["updated_at"] = time.time()
    keys = ",".join(f"{k}=?" for k in fields)
    with _lock, conn() as c:
        c.execute(f"UPDATE jobs SET {keys} WHERE id=?", (*fields.values(), job_id))

def append_log(job_id: str, line: str):
    with _lock, conn() as c:
        c.execute(
            "UPDATE jobs SET log=log||?, updated_at=? WHERE id=?",
            (line + "\n", time.time(), job_id),
        )

def get_job(job_id: str):
    with conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

def list_recent(limit: int = 12):
    with conn() as c:
        rows = c.execute(
            "SELECT id, prompt, status, video_path, created_at FROM jobs "
            "WHERE status='done' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

def count_active():
    with conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM jobs WHERE status IN ('queued','drafting','rendering')"
        ).fetchone()[0]

def count_by_ip_since(ip: str, since_ts: float):
    with conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM jobs WHERE ip=? AND created_at>=?",
            (ip, since_ts),
        ).fetchone()[0]

def reap_orphans(reason: str = "service restarted"):
    """Mark non-terminal jobs as failed (called at startup)."""
    now = time.time()
    with _lock, conn() as c:
        c.execute(
            "UPDATE jobs SET status='failed', error=?, updated_at=? "
            "WHERE status IN ('queued','drafting','rendering')",
            (reason, now),
        )

def ip_has_active(ip: str):
    with conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM jobs WHERE ip=? AND status IN ('queued','drafting','rendering')",
            (ip,),
        ).fetchone()[0] > 0
