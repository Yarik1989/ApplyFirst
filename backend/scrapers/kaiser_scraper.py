import logging
from typing import Iterable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper, Job

log = logging.getLogger(__name__)


# Roseville, CA coordinates — used in PhenomPeople URL path for geo-filtering.
# Kaiser's JS applies the geo filter client-side, so the static HTML still
# returns a generic list; we apply `matches_local_area()` post-hoc.
ROSEVILLE_LAT_PATH = "38x75208"
ROSEVILLE_LNG_PATH = "-121x28801"


class KaiserScraper(BaseScraper):
    source = "kaiser"
    base_url = "https://www.kaiserpermanentejobs.org"
    search_url = (
        "https://www.kaiserpermanentejobs.org/search-jobs/"
        f"Registered%20Nurse/Roseville%2C%20CA/641/1/"
        f"6252001-5332921-5391959/{ROSEVILLE_LAT_PATH}/{ROSEVILLE_LNG_PATH}/25/2"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }

    async def fetch(self) -> Iterable[Job]:
        async with httpx.AsyncClient(
            timeout=20, headers=self.headers, follow_redirects=True
        ) as client:
            resp = await client.get(self.search_url)
            resp.raise_for_status()
            html = resp.text

        soup = BeautifulSoup(html, "html.parser")
        jobs: list[Job] = []
        for li in soup.select("section#search-results-list li"):
            a = li.find("a", href=True)
            if not a:
                continue
            title_el = li.find("h2") or li.find("h3")
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
            loc_el = li.select_one(".job-location, .location")
            location = loc_el.get_text(strip=True) if loc_el else ""
            url = urljoin(self.base_url, a["href"])
            posted = ""
            posted_el = li.select_one("time, .job-date, .date-posted")
            if posted_el:
                posted = posted_el.get("datetime") or posted_el.get_text(strip=True)
            jobs.append(Job(
                source=self.source,
                title=title,
                company="Kaiser Permanente",
                location=location,
                url=url,
                posted_at=posted,
            ))
        # Kaiser's PhenomPeople geo URL is advisory only; results sometimes
        # leak in jobs from Moreno Valley, Oregon, etc. Filter to Sac metro.
        local = [j for j in jobs if j.matches_local_area()]
        log.info(
            "kaiser: parsed %d jobs, %d in local area", len(jobs), len(local),
        )
        return local
