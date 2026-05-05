from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.ai.scorer import ScoreResult, _build_system, _build_user, score_job
from backend.scrapers.base import Job


def _fake_client_returning(result: ScoreResult):
    client = MagicMock()
    response = MagicMock()
    response.parsed_output = result
    client.messages.parse = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_score_job_returns_parsed_output():
    job = Job(
        source="indeed",
        title="Registered Nurse — Neurology",
        company="Kaiser",
        location="Roseville, CA",
        url="https://x/1",
        description="RN needed for neurology unit, telemetry experience required.",
    )
    expected = ScoreResult(
        score=85,
        matched_keywords=["RN", "telemetry"],
        missing_keywords=["stroke protocol"],
        rationale="Strong RN + telemetry match; stroke protocol not called out.",
    )
    client = _fake_client_returning(expected)

    result = await score_job(job, resume={"name": "Test"}, client=client)

    assert result.score == 85
    assert "telemetry" in result.matched_keywords
    client.messages.parse.assert_awaited_once()


@pytest.mark.asyncio
async def test_score_job_sends_resume_in_cached_system_block():
    job = Job(source="indeed", title="RN", company="X", location="Y", url="https://x/1")
    expected = ScoreResult(score=50, matched_keywords=[], missing_keywords=[], rationale="ok")
    client = _fake_client_returning(expected)

    resume = {"name": "Hanna", "keywords": ["RN"]}
    await score_job(job, resume=resume, client=client)

    kwargs = client.messages.parse.await_args.kwargs
    system = kwargs["system"]
    assert isinstance(system, list) and len(system) == 1
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert "Hanna" in system[0]["text"]


def test_build_user_includes_all_job_fields():
    job = Job(
        source="linkedin",
        title="Med-Surg RN",
        company="Sutter",
        location="Sacramento, CA",
        url="https://x/1",
        description="3 years experience required.",
    )
    text = _build_user(job)
    assert "Med-Surg RN" in text
    assert "Sutter" in text
    assert "Sacramento" in text
    assert "3 years experience" in text


def test_build_system_uses_deterministic_json():
    s1 = _build_system({"b": 2, "a": 1})
    s2 = _build_system({"a": 1, "b": 2})
    assert s1[0]["text"] == s2[0]["text"]
