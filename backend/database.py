from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    job_id      TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    company     TEXT,
    location    TEXT,
    url         TEXT NOT NULL,
    description TEXT,
    first_seen  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | skipped
    sent_at     TEXT NOT NULL,
    acted_at    TEXT,
    FOREIGN KEY (job_id) REFERENCES seen_jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_sent_at ON alerts(sent_at);
"""


async def _migrate(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(seen_jobs)")
    cols = {row[1] for row in await cur.fetchall()}
    if "location" not in cols:
        await db.execute("ALTER TABLE seen_jobs ADD COLUMN location TEXT")
    if "description" not in cols:
        await db.execute("ALTER TABLE seen_jobs ADD COLUMN description TEXT")


def _ensure_dir() -> None:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)


async def init_db() -> None:
    _ensure_dir()
    async with aiosqlite.connect(settings.database_path) as db:
        await db.executescript(SCHEMA)
        await _migrate(db)
        await db.commit()


async def is_seen(job_id: str) -> bool:
    async with aiosqlite.connect(settings.database_path) as db:
        cur = await db.execute("SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,))
        row = await cur.fetchone()
        return row is not None


async def mark_seen(
    job_id: str,
    source: str,
    title: str,
    company: str,
    url: str,
    location: str = "",
    description: str = "",
) -> None:
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO seen_jobs "
            "(job_id, source, title, company, location, url, description, first_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, source, title, company, location, url, description, _now()),
        )
        await db.commit()


async def get_job(job_id: str) -> dict | None:
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT job_id, source, title, company, location, url, description "
            "FROM seen_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_alert_job_id(alert_id: int) -> str | None:
    async with aiosqlite.connect(settings.database_path) as db:
        cur = await db.execute("SELECT job_id FROM alerts WHERE id = ?", (alert_id,))
        row = await cur.fetchone()
        return row[0] if row else None


async def list_applications(status: str = "approved", limit: int | None = None) -> list[dict]:
    query = (
        "SELECT a.id, a.status, a.acted_at, a.sent_at, "
        "j.title, j.company, j.location, j.source, j.url "
        "FROM alerts a JOIN seen_jobs j ON a.job_id = j.job_id "
        "WHERE a.status = ? "
        "ORDER BY COALESCE(a.acted_at, a.sent_at) DESC"
    )
    params: tuple = (status,)
    if limit:
        query += " LIMIT ?"
        params = (status, limit)
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def record_alert(job_id: str) -> int:
    async with aiosqlite.connect(settings.database_path) as db:
        cur = await db.execute(
            "INSERT INTO alerts (job_id, status, sent_at) VALUES (?, 'pending', ?)",
            (job_id, _now()),
        )
        await db.commit()
        return cur.lastrowid


async def set_alert_status(alert_id: int, status: str) -> None:
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE alerts SET status = ?, acted_at = ? WHERE id = ?",
            (status, _now(), alert_id),
        )
        await db.commit()


async def applies_today_count() -> int:
    today = _today()
    async with aiosqlite.connect(settings.database_path) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM alerts WHERE status = 'approved' AND substr(acted_at, 1, 10) = ?",
            (today,),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0
