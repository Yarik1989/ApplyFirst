import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _csv(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")

    poll_interval_minutes: int = int(os.getenv("POLL_INTERVAL_MINUTES", "5"))
    max_applies_per_day: int = int(os.getenv("MAX_APPLIES_PER_DAY", "15"))
    min_ats_score_threshold: int = int(os.getenv("MIN_ATS_SCORE_THRESHOLD", "60"))

    # JobSpy lookback window — only return jobs posted within the last N hours.
    # 24 = today + overnight buffer. Lower for fresher-only; higher to widen.
    jobspy_hours_old: int = int(os.getenv("JOBSPY_HOURS_OLD", "24"))

    # Max age of a job posting before we suppress the alert (hours).
    # Jobs older than this are marked seen but NOT sent to Telegram.
    # 0 = disabled (alert regardless of age). Default 6h = "first 10 applicants" window.
    max_job_age_hours: int = int(os.getenv("MAX_JOB_AGE_HOURS", "6"))

    notify_delay_min_seconds: int = int(os.getenv("NOTIFY_DELAY_MIN_SECONDS", "120"))
    notify_delay_max_seconds: int = int(os.getenv("NOTIFY_DELAY_MAX_SECONDS", "480"))

    # Quiet hours — alerts within this window are deferred until quiet_hours_end.
    # Set start == end to disable. Hours are 0–23 in SEARCH_TIMEZONE.
    quiet_hours_start: int = int(os.getenv("QUIET_HOURS_START", "22"))
    quiet_hours_end: int = int(os.getenv("QUIET_HOURS_END", "7"))

    search_keywords: list[str] = field(default_factory=lambda: _csv(
        "SEARCH_KEYWORDS", "Registered Nurse,RN,Med-Surg,Acute Care,Neurology"
    ))
    search_location: str = os.getenv("SEARCH_LOCATION", "Roseville CA")
    search_radius_miles: int = int(os.getenv("SEARCH_RADIUS_MILES", "25"))
    local_cities: list[str] = field(default_factory=lambda: _csv(
        "SEARCH_LOCAL_CITIES",
        "Roseville,Rocklin,Lincoln,Loomis,Granite Bay,Citrus Heights,Fair Oaks,"
        "Orangevale,Carmichael,Antelope,Rio Linda,North Highlands,Arden-Arcade,"
        "Sacramento,Folsom,Rancho Cordova,Elk Grove,West Sacramento,Davis,Woodland,Auburn",
    ))
    search_timezone: str = os.getenv("SEARCH_TIMEZONE", "America/Los_Angeles")

    database_path: str = os.getenv("DATABASE_PATH", "./data/applyfirst.db")

    exclude_keywords: tuple[str, ...] = (
        "LVN", "Licensed Vocational Nurse", "Vocational Nurse",
        "CNA", "NP", "Nurse Practitioner",
        # Senior RN levels (II / III / IV) require 1+ years acute experience.
        "Registered Nurse II", "Registered Nurse III", "Registered Nurse IV",
        "RN II", "RN III", "RN IV",
        "Nurse II", "Nurse III", "Nurse IV",
        "CLIN NURSE 2", "CLIN NURSE 3", "CLIN NURSE 4",
    )

    def validate(self) -> None:
        missing = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        if missing:
            raise RuntimeError(
                f"Missing required env vars: {', '.join(missing)}. "
                "Copy .env.example to .env and fill them in."
            )


settings = Settings()
