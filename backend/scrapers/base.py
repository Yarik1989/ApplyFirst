import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo
from email.utils import parsedate_to_datetime
from typing import Iterable
from zoneinfo import ZoneInfo

from ..config import settings

log = logging.getLogger(__name__)


def _local_tz() -> tzinfo:
    try:
        return ZoneInfo(settings.search_timezone)
    except Exception:
        return timezone.utc


def _parse_date(raw: str) -> datetime | None:
    if not raw:
        return None
    local = _local_tz()
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=local)
        return dt
    except (TypeError, ValueError):
        pass
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=local)
        return dt
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=local)
            return dt
        except ValueError:
            continue
    return None


@dataclass
class Job:
    source: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    posted_at: str = ""
    job_id: str = field(init=False)
    posted_at_dt: datetime | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        key = f"{self.source}|{self.url}".encode("utf-8")
        self.job_id = hashlib.sha1(key).hexdigest()
        self.posted_at_dt = _parse_date(self.posted_at)

    def matches_search(self) -> bool:
        haystack = f"{self.title} {self.description}".lower()
        if any(bad.lower() in haystack for bad in settings.exclude_keywords):
            return False
        # All travel nursing titles start with "Travel" — block universally.
        if self.title.lower().startswith("travel"):
            return False
        return any(kw.lower() in haystack for kw in settings.search_keywords)

    def matches_local_area(self) -> bool:
        """True if the job's location string mentions a Sacramento-metro city."""
        loc = (self.location or "").lower()
        if not loc:
            return False
        return any(city.lower() in loc for city in settings.local_cities)

    def is_today(self, tz: tzinfo | None = None) -> bool:
        if not self.posted_at_dt:
            return False
        tz = tz or _local_tz()
        return self.posted_at_dt.astimezone(tz).date() == datetime.now(tz).date()

    def is_fresh(self, max_hours: int = 0) -> bool:
        """True if the posting is within max_hours of now, or if we can't tell."""
        if max_hours <= 0 or not self.posted_at_dt:
            return True  # no date → assume fresh; disabled → always fresh
        age = (datetime.now(timezone.utc) - self.posted_at_dt.astimezone(timezone.utc))
        return age.total_seconds() < max_hours * 3600


class BaseScraper(ABC):
    source: str = "unknown"

    @abstractmethod
    async def fetch(self) -> Iterable[Job]:
        """Return an iterable of Job objects discovered on this source."""

    async def safe_fetch(self) -> list[Job]:
        try:
            jobs = list(await self.fetch())
        except Exception as exc:
            log.exception("Scraper %s failed: %s", self.source, exc)
            return []
        filtered = [j for j in jobs if j.matches_search()]
        log.info("%s: fetched=%d matched=%d", self.source, len(jobs), len(filtered))
        return filtered


class DisabledScraper(BaseScraper):
    """Placeholder for sources that require Playwright or paid APIs.

    Returns no jobs; logs once per poll. Real implementation deferred to Phase 3.
    """
    note: str = ""

    async def fetch(self) -> Iterable[Job]:
        log.info("%s: disabled — %s", self.source, self.note)
        return []
