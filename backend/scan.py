"""Terminal-only scanner — poll sources, score jobs, print a ranked table.

Examples:
    python -m backend.scan                         # all sources, score, rank by score
    python -m backend.scan --top 10                # top 10 matches
    python -m backend.scan --local                 # filter to Sacramento-metro cities
    python -m backend.scan --today                 # only jobs posted today
    python -m backend.scan --newest                # sort by posted date desc (no scoring needed)
    python -m backend.scan --source kaiser
    python -m backend.scan --no-score
    python -m backend.scan --mark-seen             # persist results to seen_jobs DB
"""
import argparse
import asyncio
import logging
import sys
import textwrap
from datetime import datetime, timezone

from .ai.client import MissingAPIKeyError
from .ai.scorer import ScoreResult, load_resume, score_job
from .config import settings
from .database import init_db, mark_seen
from .scrapers import all_scrapers
from .scrapers.base import Job

log = logging.getLogger("applyfirst.scan")


COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "cyan": "\033[36m",
    "magenta": "\033[35m",
}


def _color_score(score: int) -> str:
    if score >= settings.min_ats_score_threshold:
        c = COLORS["green"]
    elif score >= 40:
        c = COLORS["yellow"]
    else:
        c = COLORS["red"]
    return f"{c}{COLORS['bold']}{score:>3}/100{COLORS['reset']}"


def _fmt_posted(job: Job) -> str:
    if job.posted_at_dt:
        now = datetime.now(timezone.utc)
        delta = now - job.posted_at_dt
        if delta.days == 0:
            hours = int(delta.total_seconds() / 3600)
            return f"today ({hours}h ago)" if hours > 0 else "just now"
        if delta.days == 1:
            return "yesterday"
        if delta.days < 7:
            return f"{delta.days}d ago"
        return job.posted_at_dt.strftime("%Y-%m-%d")
    return job.posted_at or "—"


def _print_job(rank: int, job: Job, score: ScoreResult | None) -> None:
    head = f"{COLORS['bold']}[{rank}] {job.title}{COLORS['reset']}"
    if score is not None:
        head = f"{_color_score(score.score)}  {head}"
    print(head)
    meta = f"  {job.company or job.source.title()}"
    if job.location:
        meta += f" — {job.location}"
    meta += f"  {COLORS['dim']}({job.source}){COLORS['reset']}"
    posted = _fmt_posted(job)
    if posted != "—":
        meta += f"  {COLORS['magenta']}⏱ {posted}{COLORS['reset']}"
    print(meta)
    print(f"  {COLORS['cyan']}{job.url}{COLORS['reset']}")
    if score is not None:
        print(f"  {COLORS['dim']}rationale:{COLORS['reset']} {score.rationale}")
        if score.matched_keywords:
            kws = ", ".join(score.matched_keywords[:10])
            print(f"  {COLORS['green']}✓ matched:{COLORS['reset']} {kws}")
        if score.missing_keywords:
            kws = ", ".join(score.missing_keywords[:10])
            print(f"  {COLORS['red']}✗ missing:{COLORS['reset']} {kws}")
    if job.description:
        snippet = textwrap.shorten(job.description, width=200, placeholder="…")
        print(f"  {COLORS['dim']}{snippet}{COLORS['reset']}")
    print()


async def _score_safe(job: Job, resume: dict) -> ScoreResult | None:
    try:
        return await score_job(job, resume=resume)
    except MissingAPIKeyError:
        return None
    except Exception as exc:
        log.exception("Scoring failed for %s: %s", job.title, exc)
        return None


async def scan(args: argparse.Namespace) -> int:
    scrapers = all_scrapers()
    print(f"{COLORS['bold']}Scanning {len(scrapers)} scraper(s)...{COLORS['reset']}\n")
    per_scraper = await asyncio.gather(*(s.safe_fetch() for s in scrapers))

    all_jobs: list[Job] = [j for group in per_scraper for j in group]

    # Diagnostic summary — group by Job.source so JobSpy's aggregated output
    # breaks out as indeed/linkedin individually.
    from collections import Counter
    source_counts = Counter(j.source for j in all_jobs)
    for scraper in scrapers:
        if scraper.source == "jobspy":
            for site in ("indeed", "linkedin", "zip_recruiter", "glassdoor", "google"):
                n = source_counts.get(site, 0)
                color = COLORS["green"] if n else COLORS["dim"]
                print(f"  {site:<14} {color}{n} jobs{COLORS['reset']}")
        else:
            n = source_counts.get(scraper.source, 0)
            color = COLORS["green"] if n else COLORS["dim"]
            print(f"  {scraper.source:<14} {color}{n} jobs{COLORS['reset']}")
    print()

    if args.source:
        before = len(all_jobs)
        all_jobs = [j for j in all_jobs if j.source == args.source]
        print(f"{COLORS['dim']}--source {args.source}: kept {len(all_jobs)}/{before}{COLORS['reset']}")

    if args.local:
        before = len(all_jobs)
        all_jobs = [j for j in all_jobs if j.matches_local_area()]
        print(f"{COLORS['dim']}--local: kept {len(all_jobs)}/{before} in Sacramento metro{COLORS['reset']}")

    if args.today:
        before = len(all_jobs)
        all_jobs = [j for j in all_jobs if j.is_today()]
        print(f"{COLORS['dim']}--today: kept {len(all_jobs)}/{before} posted today{COLORS['reset']}")

    if not all_jobs:
        print("\nNo jobs match the current filters.")
        return 0

    if args.mark_seen:
        await init_db()

    if not args.no_score and not settings.anthropic_api_key:
        print(
            f"{COLORS['yellow']}{COLORS['bold']}⚠ ANTHROPIC_API_KEY not set "
            f"— ATS scoring disabled, jobs will be shown unranked. "
            f"Pass --no-score to silence this, or set the key in .env.{COLORS['reset']}\n"
        )

    resume = load_resume() if not args.no_score else None
    scored: list[tuple[Job, ScoreResult | None]] = []
    for job in all_jobs:
        score = None if args.no_score else await _score_safe(job, resume)
        scored.append((job, score))
        if args.mark_seen:
            await mark_seen(
                job.job_id, job.source, job.title, job.company,
                job.url, job.location, job.description,
            )

    def sort_key(row):
        job, score = row
        if args.newest:
            # Sort by posted date desc (unknown dates last)
            return (
                0 if job.posted_at_dt else 1,
                -(job.posted_at_dt.timestamp() if job.posted_at_dt else 0),
            )
        # Default: score desc, then posted date desc
        return (
            -(score.score if score else -1),
            0 if job.posted_at_dt else 1,
            -(job.posted_at_dt.timestamp() if job.posted_at_dt else 0),
        )

    scored.sort(key=sort_key)

    if args.top:
        scored = scored[: args.top]

    print()
    for i, (job, score) in enumerate(scored, 1):
        _print_job(i, job, score)

    non_null = [s for _, s in scored if s is not None]
    if non_null:
        avg = sum(s.score for s in non_null) / len(non_null)
        above = sum(1 for s in non_null if s.score >= settings.min_ats_score_threshold)
        print(
            f"{COLORS['bold']}Summary:{COLORS['reset']} {len(non_null)} scored, "
            f"avg {avg:.1f}, {above} above threshold ({settings.min_ats_score_threshold})"
        )
    else:
        print(f"{COLORS['bold']}Summary:{COLORS['reset']} {len(scored)} jobs shown")
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="ApplyFirst terminal scanner")
    parser.add_argument("--source", help="Only scan this source")
    parser.add_argument("--top", type=int, help="Show top N results")
    parser.add_argument("--local", action="store_true",
                        help="Filter to Sacramento-metro cities (see SEARCH_LOCAL_CITIES)")
    parser.add_argument("--today", action="store_true",
                        help="Only jobs posted today")
    parser.add_argument("--newest", action="store_true",
                        help="Sort by posted date desc (default sorts by score desc)")
    parser.add_argument("--no-score", action="store_true", help="Skip ATS scoring")
    parser.add_argument("--mark-seen", action="store_true", help="Persist to seen_jobs DB")
    args = parser.parse_args()

    return asyncio.run(scan(args))


if __name__ == "__main__":
    sys.exit(main())
