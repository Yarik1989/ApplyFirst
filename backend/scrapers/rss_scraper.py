"""RSS-based scrapers.

Status (as of 2026-04):
- Indeed deprecated its public RSS feed — returns 404. Disabled.
- LinkedIn does not offer public RSS for job searches. Disabled.
- ZipRecruiter does not offer public RSS for job searches. Disabled.

When Phase 3 adds Playwright, replace these with headless-browser scrapers
or wire in a paid API (Adzuna, JobSpy, etc.).
"""
from .base import DisabledScraper


class IndeedRSS(DisabledScraper):
    source = "indeed"
    note = "Indeed deprecated public RSS (404). Use Playwright or paid API."


class LinkedInRSS(DisabledScraper):
    source = "linkedin"
    note = "LinkedIn has no public RSS. Requires Voyager API auth or Playwright."


class ZipRecruiterRSS(DisabledScraper):
    source = "ziprecruiter"
    note = "ZipRecruiter has no public RSS. Requires partner API or Playwright."
