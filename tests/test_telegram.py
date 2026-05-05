from backend.notifier.telegram_bot import _format
from backend.scrapers.base import Job


def test_format_escapes_html():
    job = Job(
        source="indeed",
        title="RN <script>alert(1)</script>",
        company="AT&T Health",
        location="Roseville, CA",
        url="https://example.com/job?id=1&x=2",
    )
    text = _format(job, score=None)
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "AT&amp;T Health" in text
    assert "https://example.com/job?id=1&amp;x=2" in text


def test_format_includes_score_when_provided():
    from backend.ai.scorer import ScoreResult

    job = Job(
        source="indeed",
        title="RN",
        company="Kaiser",
        location="Roseville, CA",
        url="https://x/1",
    )
    score = ScoreResult(
        score=82,
        matched_keywords=["RN", "telemetry"],
        missing_keywords=["stroke"],
        rationale="Strong RN match.",
    )
    text = _format(job, score=score)
    assert "82/100" in text
    assert "Strong RN match" in text
    assert "RN, telemetry" in text
    assert "stroke" in text


def test_format_includes_source_and_title():
    job = Job(
        source="kaiser",
        title="Med-Surg RN",
        company="Kaiser Permanente",
        location="Roseville, CA",
        url="https://kp.example/1",
    )
    text = _format(job, score=None)
    assert "Med-Surg RN" in text
    assert "kaiser" in text
    assert "Kaiser Permanente" in text
