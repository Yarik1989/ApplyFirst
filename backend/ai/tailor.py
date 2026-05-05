import json
import logging

import anthropic
from pydantic import BaseModel, Field

from ..config import settings
from ..scrapers.base import Job
from .client import get_client

log = logging.getLogger(__name__)


class ResumePatch(BaseModel):
    path: str = Field(description="JSON Pointer into the resume, e.g. /target_roles/0")
    original: str = Field(description="Current string value at that path")
    replacement: str = Field(description="Proposed replacement string")
    reason: str = Field(description="Why this change helps ATS alignment")


class TailorResult(BaseModel):
    patches: list[ResumePatch]


TAILOR_SYSTEM_TEMPLATE = """You tailor a candidate's resume to maximize ATS keyword match for a specific job posting.

Return a minimal JSON diff — do NOT rewrite the resume. Only propose wording changes on existing string fields: reorder keywords, adjust phrasing, emphasize relevant skills. Never fabricate experience, credentials, or employment dates.

Paths use JSON Pointer syntax relative to the resume root. Array indices are numeric, object keys are literal. Examples:
- /target_roles/0
- /keywords/5
- /experience/0/title

Constraints:
- Return 0-8 high-impact patches. Fewer is better.
- `original` must match the current value at `path` exactly.
- `replacement` must be a plausible, truthful variant of `original`.

CANDIDATE RESUME (JSON):
{resume_json}"""


def _build_system(resume: dict) -> list[dict]:
    resume_text = json.dumps(resume, indent=2, sort_keys=True)
    return [{
        "type": "text",
        "text": TAILOR_SYSTEM_TEMPLATE.format(resume_json=resume_text),
        "cache_control": {"type": "ephemeral"},
    }]


def _build_user(job: Job) -> str:
    return (
        f"Tailor the resume for this posting.\n\n"
        f"Job title: {job.title}\n"
        f"Company: {job.company or '(unknown)'}\n"
        f"Location: {job.location or '(unknown)'}\n\n"
        f"Description:\n{job.description or '(not provided)'}"
    )


async def tailor_resume(
    job: Job,
    resume: dict,
    client: anthropic.AsyncAnthropic | None = None,
) -> list[ResumePatch]:
    client = client or get_client()

    response = await client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=4000,
        system=_build_system(resume),
        messages=[{"role": "user", "content": _build_user(job)}],
        output_format=TailorResult,
    )
    patches = response.parsed_output.patches
    log.info("Tailor produced %d patches for %s", len(patches), job.title)
    return patches
