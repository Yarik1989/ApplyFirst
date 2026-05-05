"""UC Davis Health careers.

Status: UCOP's PeopleSoft + Health's Workday portal are both JS-rendered and
behind auth/CSRF tokens. Static scraping not viable. Disabled until Phase 3.
"""
from .base import DisabledScraper


class UCDavisScraper(DisabledScraper):
    source = "ucdavis"
    note = "PeopleSoft/Workday — needs Playwright."
