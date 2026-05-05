from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.ai.tailor import ResumePatch, TailorResult, tailor_resume
from backend.scrapers.base import Job


@pytest.mark.asyncio
async def test_tailor_returns_patches():
    job = Job(
        source="indeed",
        title="Telemetry RN",
        company="Kaiser",
        location="Roseville, CA",
        url="https://x/1",
        description="Telemetry and cardiac monitoring required.",
    )
    expected = TailorResult(patches=[
        ResumePatch(
            path="/target_roles/0",
            original="Registered Nurse",
            replacement="Registered Nurse — Telemetry",
            reason="Posting emphasizes telemetry",
        ),
    ])
    client = MagicMock()
    response = MagicMock()
    response.parsed_output = expected
    client.messages.parse = AsyncMock(return_value=response)

    resume = {"target_roles": ["Registered Nurse"]}
    patches = await tailor_resume(job, resume=resume, client=client)

    assert len(patches) == 1
    assert patches[0].path == "/target_roles/0"
    client.messages.parse.assert_awaited_once()
