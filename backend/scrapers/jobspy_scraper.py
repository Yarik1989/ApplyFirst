"""JobSpy-powered aggregator for Indeed, LinkedIn, ZipRecruiter, Glassdoor, Google.

JobSpy (https://github.com/speedyapply/JobSpy) handles anti-bot headers and
session management better than hand-rolled HTTP. No API keys required.

Current reliability (as of probe, 2026-04):
- indeed:       works
- linkedin:     works
- zip_recruiter: 403 Forbidden (Cloudflare)
- glassdoor:    API signature changed, returns 400
- google:       requires google_search_term, unreliable

We request all five and let the ones that work return data. Each returned Job
carries `source=indeed|linkedin|...` so the CLI shows a per-site breakdown.
"""
import asyncio
import logging
from typing import Iterable

from ..config import settings
from .base import BaseScraper, Job

log = logging.getLogger(__name__)


DEFAULT_SITES = ["indeed", "linkedin", "zip_recruiter", "glassdoor", "google"]


class JobSpyScraper(BaseScraper):
    source = "jobspy"

    def __init__(self, sites: list[str] | None = None, results_per_site: int = 25,
                 hours_old: int | None = None) -> None:
        self.sites = sites if sites is not None else list(DEFAULT_SITES)
        self.results_per_site = results_per_site
        self.hours_old = hours_old if hours_old is not None else settings.jobspy_hours_old

    async def fetch(self) -> Iterable[Job]:
        df = await asyncio.to_thread(self._scrape_sync)
        if df is None or len(df) == 0:
            return []

        records = df.to_dict(orient="records")
        jobs: list[Job] = []
        for r in records:
            url = self._str(r.get("job_url"))
            if not url:
                continue
            site = self._str(r.get("site")) or "jobspy"
            title = self._str(r.get("title"))
            company = self._str(r.get("company"))
            location = self._str(r.get("location"))
            description = self._str(r.get("description"))[:4000]
            posted_at = self._str(r.get("date_posted"))
            jobs.append(Job(
                source=site,
                title=title,
                company=company,
                location=location,
                url=url,
                description=description,
                posted_at=posted_at,
            ))
        return jobs

    def _scrape_sync(self):
        from jobspy import scrape_jobs

        keyword = settings.search_keywords[0] if settings.search_keywords else "registered nurse"
        try:
            return scrape_jobs(
                site_name=self.sites,
                search_term=keyword,
                google_search_term=f"{keyword} jobs near {settings.search_location}",
                location=settings.search_location,
                distance=settings.search_radius_miles,
                results_wanted=self.results_per_site,
                hours_old=self.hours_old,
                verbose=0,
            )
        except Exception as exc:
            log.warning("JobSpy call failed: %s", exc)
            return None

    @staticmethod
    def _str(v) -> str:
        if v is None:
            return ""
        s = str(v)
        if s.lower() in ("nan", "nat", "none"):
            return ""
        return s.strip()
