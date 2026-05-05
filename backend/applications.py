"""List jobs you approved for application.

Usage:
    python -m backend.applications                 # approved jobs, newest first
    python -m backend.applications --status pending
    python -m backend.applications --csv > apps.csv
    python -m backend.applications --limit 20
"""
import argparse
import asyncio
import csv
import sys
from datetime import datetime

from .database import list_applications


COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "green": "\033[32m",
    "cyan": "\033[36m",
}


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso[:16]


def _print_table(rows: list[dict]) -> None:
    if not rows:
        print("No applications found.")
        return

    print(f"{COLORS['bold']}{'#':<3}  {'Date':<17}  {'Company':<22}  {'Title':<40}  Source{COLORS['reset']}")
    print(COLORS["dim"] + "─" * 100 + COLORS["reset"])
    for i, r in enumerate(rows, 1):
        date = _fmt_date(r["acted_at"] or r["sent_at"])
        company = (r["company"] or r["source"]).title()[:22]
        title = (r["title"] or "")[:40]
        source = r["source"]
        print(f"{i:<3}  {date:<17}  {company:<22}  {title:<40}  {COLORS['dim']}{source}{COLORS['reset']}")
        print(f"     {COLORS['cyan']}{r['url']}{COLORS['reset']}")
    print()
    print(f"{COLORS['bold']}{len(rows)} application(s){COLORS['reset']}")


def _write_csv(rows: list[dict]) -> None:
    writer = csv.writer(sys.stdout)
    writer.writerow(["date", "status", "company", "title", "location", "source", "url"])
    for r in rows:
        writer.writerow([
            _fmt_date(r["acted_at"] or r["sent_at"]),
            r["status"],
            r["company"] or "",
            r["title"] or "",
            r["location"] or "",
            r["source"],
            r["url"],
        ])


async def run(args: argparse.Namespace) -> int:
    rows = await list_applications(status=args.status, limit=args.limit)
    if args.csv:
        _write_csv(rows)
    else:
        _print_table(rows)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="List application records")
    parser.add_argument(
        "--status", default="approved",
        choices=["approved", "skipped", "pending"],
        help="Alert status to list (default: approved)",
    )
    parser.add_argument("--limit", type=int, help="Max rows to return")
    parser.add_argument("--csv", action="store_true", help="Output as CSV to stdout")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
