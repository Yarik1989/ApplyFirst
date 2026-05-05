import asyncio
import logging
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .ai.client import MissingAPIKeyError
from .ai.scorer import ScoreResult, load_resume, score_job
from .config import settings
from .database import init_db, is_seen, mark_seen
from .notifier.telegram_bot import TelegramNotifier
from .scrapers import all_scrapers
from .scrapers.base import Job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("applyfirst")


async def _score_safe(job: Job, resume: dict) -> ScoreResult | None:
    try:
        return await score_job(job, resume=resume)
    except MissingAPIKeyError:
        return None
    except Exception as exc:
        log.exception("Scoring failed for %s: %s", job.title, exc)
        return None


async def poll_once(notifier: TelegramNotifier) -> None:
    log.info("Polling all sources...")
    scrapers = all_scrapers()
    results = await asyncio.gather(*(s.safe_fetch() for s in scrapers))

    new_jobs: list[Job] = []
    stale = 0
    for jobs in results:
        for job in jobs:
            if await is_seen(job.job_id):
                continue
            await mark_seen(
                job.job_id, job.source, job.title, job.company,
                job.url, job.location, job.description,
            )
            if not job.is_fresh(settings.max_job_age_hours):
                stale += 1
                continue
            new_jobs.append(job)

    log.info(
        "Found %d new matching jobs (%d skipped as stale >%dh)",
        len(new_jobs), stale, settings.max_job_age_hours,
    )
    if not new_jobs:
        return

    resume = load_resume()
    scored: list[tuple[Job, ScoreResult | None]] = []
    for job in new_jobs:
        result = await _score_safe(job, resume)
        if result is not None and result.score < settings.min_ats_score_threshold:
            log.info(
                "Skipping %s (score %d < threshold %d)",
                job.title, result.score, settings.min_ats_score_threshold,
            )
            continue
        scored.append((job, result))

    log.info("Sending %d alerts after scoring", len(scored))
    for j, s in scored:
        asyncio.create_task(notifier.send_job(j, score=s))


async def run() -> None:
    settings.validate()
    await init_db()

    notifier = TelegramNotifier()
    await notifier.start()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_once,
        "interval",
        minutes=settings.poll_interval_minutes,
        args=[notifier],
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("Scheduler started — polling every %d min", settings.poll_interval_minutes)

    asyncio.create_task(poll_once(notifier))

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    try:
        await stop_event.wait()
    finally:
        log.info("Shutting down...")
        scheduler.shutdown(wait=False)
        await notifier.stop()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
