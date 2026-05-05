"""Sutter Health careers — jobs.sutterhealth.org.

Status: page is a JavaScript-rendered SPA. Static HTML has no job listings.
Disabled until Phase 3 (Playwright). Probe confirmed: 114KB of JS, 0 jobs
in the DOM with `curl`-fetched HTML.
"""
from .base import DisabledScraper


class SutterScraper(DisabledScraper):
    source = "sutter"
    note = "SPA — static HTML has no jobs. Needs Playwright."
