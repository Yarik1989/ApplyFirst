import json
import logging

import anthropic
from pydantic import BaseModel, Field

from ..config import PROJECT_ROOT, settings
from ..scrapers.base import Job
from .client import get_client

log = logging.getLogger(__name__)


class ScoreResult(BaseModel):
    score: int = Field(ge=0, le=100)
    matched_keywords: list[str]
    missing_keywords: list[str]
    rationale: str


SCORING_SYSTEM_TEMPLATE = """You are an expert ATS (Applicant Tracking System) scoring assistant.

Score how well the candidate's resume matches a job posting on a 0-100 scale:
- 0-40: poor fit (different role, missing critical credentials)
- 40-60: marginal fit (transferable skills but notable gaps)
- 60-80: good fit (meets most requirements, some gaps)
- 80-100: excellent fit (strong keyword and experience alignment)

CANDIDATE RESUME (JSON):
{resume_json}

For the job posting the user sends, return:
- score: integer 0-100
- matched_keywords: keywords from the resume that also appear in the posting
- missing_keywords: important keywords in the posting that are absent from the resume
- rationale: one sentence explaining the score"""


def load_resume() -> dict:
    path = PROJECT_ROOT / "assets" / "resume_base.json"
    with open(path) as f:
        return json.load(f)


def _build_system(resume: dict) -> list[dict]:
    resume_text = json.dumps(resume, indent=2, sort_keys=True)
    return [{
        "type": "text",
        "text": SCORING_SYSTEM_TEMPLATE.format(resume_json=resume_text),
        "cache_control": {"type": "ephemeral"},
    }]


def _build_user(job: Job) -> str:
    return (
        f"Job title: {job.title}\n"
        f"Company: {job.company or '(unknown)'}\n"
        f"Location: {job.location or '(unknown)'}\n"
        f"Source: {job.source}\n\n"
        f"Description:\n{job.description or '(not provided)'}"
    )


async def score_job(
    job: Job,
    resume: dict | None = None,
    client: anthropic.AsyncAnthropic | None = None,
) -> ScoreResult:
    resume = resume if resume is not None else load_resume()
    client = client or get_client()

    response = await client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=2000,
        system=_build_system(resume),
        messages=[{"role": "user", "content": _build_user(job)}],
        output_format=ScoreResult,
    )
    result = response.parsed_output
    log.info("Scored %s: %d — %s", job.title, result.score, result.rationale)
    return result
