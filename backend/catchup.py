"""Send missed job alerts from the vacation period.

Finds jobs discovered in the last N days that were never alerted (skipped
as stale) and sends them to Telegram, newest first. Uses 3-second spacing
between messages to avoid Telegram rate limits.

Usage:
    python -m backend.catchup              # last 7 days, default
    python -m backend.catchup --days 14    # last 14 days
    python -m backend.catchup --dry-run    # preview without sending
"""
import argparse
import asyncio
import logging
import sys

import aiosqlite

from .config import settings
from .database import init_db, record_alert
from .notifier.telegram_bot import TelegramNotifier, _format
from .scrapers.base import Job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("applyfirst.catchup")


def _job_from_row(row: dict) -> Job:
    return Job(
        source=row["source"],
        title=row["title"],
        company=row.get("company") or "",
        location=row.get("location") or "",
        url=row["url"],
        description=row.get("description") or "",
        posted_at=row.get("first_seen") or "",
    )


async def catchup(days: int, dry_run: bool) -> int:
    await init_db()

    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT s.job_id, s.source, s.title, s.company, s.location,
                   s.url, s.description, s.first_seen
            FROM seen_jobs s
            LEFT JOIN alerts a ON a.job_id = s.job_id
            WHERE s.first_seen >= date('now', ? || ' days')
              AND s.title != '[already applied]'
              AND a.id IS NULL
            ORDER BY s.first_seen DESC
            """,
            (f"-{days}",),
        )
        rows = [dict(r) for r in await cur.fetchall()]

    if not rows:
        log.info("No missed jobs to catch up on.")
        return 0

    log.info("Found %d missed jobs from the last %d days", len(rows), days)

    if dry_run:
        for i, r in enumerate(rows, 1):
            print(f"{i:3}. [{r['source']:8}] {r['title']}")
            print(f"     {r['company']} — {r['location']}")
            print(f"     {r['url']}")
            print()
        print(f"Dry run — {len(rows)} jobs would be sent. Remove --dry-run to send.")
        return 0

    notifier = TelegramNotifier()
    await notifier.app.initialize()

    header = f"📋 <b>Catch-up: {len(rows)} jobs from the last {days} days</b>\n(newest first, while you were away)"
    await notifier.app.bot.send_message(
        chat_id=settings.telegram_chat_id,
        text=header,
        parse_mode="HTML",
    )
    await asyncio.sleep(1)

    sent = 0
    for r in rows:
        job = _job_from_row(r)
        text = _format(job, score=None)
        try:
            await notifier.app.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
            await record_alert(job.job_id)
            sent += 1
            log.info("Sent catch-up %d/%d: %s", sent, len(rows), job.title)
        except Exception as exc:
            log.warning("Failed to send %s: %s", job.title, exc)
        await asyncio.sleep(3)

    await notifier.app.shutdown()
    log.info("Catch-up complete: %d/%d sent", sent, len(rows))
    return sent


def main() -> int:
    parser = argparse.ArgumentParser(description="Send missed vacation alerts")
    parser.add_argument("--days", type=int, default=7, help="Look back N days (default 7)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    args = parser.parse_args()
    sent = asyncio.run(catchup(args.days, args.dry_run))
    return 0 if sent >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
