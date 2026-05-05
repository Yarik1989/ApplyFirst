from .base import BaseScraper, Job
from .jobspy_scraper import JobSpyScraper
from .kaiser_scraper import KaiserScraper
from .sutter_scraper import SutterScraper
from .ucdavis_scraper import UCDavisScraper
from .dignity_scraper import DignityScraper


def all_scrapers() -> list[BaseScraper]:
    return [
        JobSpyScraper(),
        KaiserScraper(),
        SutterScraper(),
        UCDavisScraper(),
        DignityScraper(),
    ]


__all__ = [
    "BaseScraper",
    "Job",
    "JobSpyScraper",
    "KaiserScraper",
    "SutterScraper",
    "UCDavisScraper",
    "DignityScraper",
    "all_scrapers",
]
