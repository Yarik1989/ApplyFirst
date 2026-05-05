"""Dignity Health / CommonSpirit careers — dignityhealthcareers.org.

Server-rendered (TalentBrew/Radancy + iCIMS). Static HTML contains the full
job list, so no Playwright needed. The location query param doesn't filter
server-side, so we pull the unfiltered set and rely on Job.matches_local_area()
plus matches_search() downstream.
"""
import logging
from typing import Iterable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..config import settings
from .base import BaseScraper, Job

log = logging.getLogger(__name__)


class DignityScraper(BaseScraper):
    source = "dignity"
    base_url = "https://www.dignityhealthcareers.org"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }

    @property
    def search_url(self) -> str:
        keyword = (settings.search_keywords[0] if settings.search_keywords
                   else "Registered Nurse").replace(" ", "+")
        location = settings.search_location.replace(" ", "+").replace(",", "%2C")
        return (
            f"{self.base_url}/search-jobs"
            f"?keywords={keyword}&location={location}"
            f"&radius={settings.search_radius_miles}"
        )

    async def fetch(self) -> Iterable[Job]:
        async with httpx.AsyncClient(
            timeout=20, headers=self.headers, follow_redirects=True
        ) as client:
            resp = await client.get(self.search_url)
            resp.raise_for_status()
            html = resp.text

        soup = BeautifulSoup(html, "html.parser")
        jobs: list[Job] = []
        for li in soup.select("li.search-results-list__item"):
            a = li.select_one("a.search-results-list__job-link")
            if not a or not a.get("href"):
                continue
            title_el = li.select_one(".search-results-list__job-title")
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
            facility_el = li.select_one(".job-facility")
            facility = facility_el.get_text(strip=True) if facility_el else "Dignity Health"
            loc_el = li.select_one(".job-location")
            location = loc_el.get_text(strip=True) if loc_el else ""
            dept_el = li.select_one(".job-department")
            department = dept_el.get_text(strip=True) if dept_el else ""
            url = urljoin(self.base_url, a["href"])
            jobs.append(Job(
                source=self.source,
                title=title,
                company=facility,
                location=location,
                url=url,
                description=department,
            ))
        # Dignity's URL doesn't honor `radius` server-side, so filter to
        # Sacramento-metro here. Otherwise we'd alert on LA/Phoenix postings.
        local = [j for j in jobs if j.matches_local_area()]
        log.info(
            "dignity: parsed %d jobs from search-results, %d in local area",
            len(jobs), len(local),
        )
        return local
