"""Pre-flight checks for the pilot.

    python -m backend.healthcheck --ping
        Send a one-shot Telegram message. Validates TELEGRAM_BOT_TOKEN +
        TELEGRAM_CHAT_ID. Exits immediately.

    python -m backend.healthcheck --alert
        Push a fake Job through the full notifier with delay=0, then keep the
        bot polling so you can click Approve/Skip and confirm the callback +
        tailored-resume delivery work. Ctrl+C to exit.
"""
import argparse
import asyncio
import logging
import sys

from .config import settings
from .database import init_db, mark_seen
from .notifier.telegram_bot import TelegramNotifier
from .scrapers.base import Job

log = logging.getLogger("applyfirst.healthcheck")


FAKE_JOB = Job(
    source="healthcheck",
    title="[TEST] Registered Nurse — Med-Surg",
    company="ApplyFirst Pilot Bot",
    location="Roseville, CA",
    url="https://example.com/healthcheck-job",
    description=(
        "This is a synthetic job posting from the ApplyFirst healthcheck. "
        "Click Approve to verify the callback handler and tailored-resume "
        "delivery. Click Skip to verify the skip path."
    ),
)


async def ping() -> int:
    settings.validate()
    notifier = TelegramNotifier()
    await notifier.app.initialize()
    try:
        await notifier.app.bot.send_message(
            chat_id=settings.telegram_chat_id,
            text="✅ ApplyFirst healthcheck — Telegram is wired up correctly.",
        )
        print("Ping sent. Check your Telegram.")
        return 0
    finally:
        await notifier.app.shutdown()


async def alert() -> int:
    settings.validate()
    await init_db()

    # Force immediate delivery for the test
    settings.notify_delay_min_seconds = 0
    settings.notify_delay_max_seconds = 0

    # Insert the fake job into seen_jobs so the Approve callback can look it up
    await mark_seen(
        FAKE_JOB.job_id, FAKE_JOB.source, FAKE_JOB.title, FAKE_JOB.company,
        FAKE_JOB.url, FAKE_JOB.location, FAKE_JOB.description,
    )

    notifier = TelegramNotifier()
    await notifier.start()
    print("Bot online. Sending fake alert…")
    await notifier.send_job(FAKE_JOB)
    print("Alert sent. Click Approve or Skip in Telegram.")
    print("Bot will keep polling for callbacks. Ctrl+C to exit.")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await notifier.stop()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="ApplyFirst Telegram healthcheck")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ping", action="store_true",
                       help="Send a one-shot Telegram message and exit")
    group.add_argument("--alert", action="store_true",
                       help="Push a fake Job through the full notifier (interactive)")
    args = parser.parse_args()

    if args.ping:
        return asyncio.run(ping())
    return asyncio.run(alert())


if __name__ == "__main__":
    sys.exit(main())
