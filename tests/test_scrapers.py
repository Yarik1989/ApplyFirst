from datetime import datetime, timedelta, timezone

from backend.scrapers.base import Job


def test_job_id_is_stable_for_same_source_and_url():
    a = Job(source="indeed", title="RN", company="X", location="Y", url="https://x/1")
    b = Job(source="indeed", title="different title", company="Z", location="W", url="https://x/1")
    assert a.job_id == b.job_id


def test_job_id_differs_across_sources():
    a = Job(source="indeed", title="RN", company="X", location="Y", url="https://x/1")
    b = Job(source="linkedin", title="RN", company="X", location="Y", url="https://x/1")
    assert a.job_id != b.job_id


def test_matches_search_accepts_rn_posting():
    job = Job(
        source="indeed",
        title="Registered Nurse – Med-Surg",
        company="Kaiser",
        location="Roseville, CA",
        url="https://x/1",
        description="Acute care RN needed",
    )
    assert job.matches_search() is True


def test_matches_search_rejects_lvn_posting():
    job = Job(
        source="indeed",
        title="LVN – Clinic",
        company="Clinic",
        location="Roseville, CA",
        url="https://x/2",
        description="Licensed Vocational Nurse",
    )
    assert job.matches_search() is False


def test_matches_search_rejects_np_posting():
    job = Job(
        source="indeed",
        title="Nurse Practitioner – Family Medicine",
        company="Clinic",
        location="Roseville, CA",
        url="https://x/3",
    )
    assert job.matches_search() is False


def test_matches_search_rejects_unrelated_posting():
    job = Job(
        source="indeed",
        title="Software Engineer",
        company="Tech Co",
        location="Roseville, CA",
        url="https://x/4",
    )
    assert job.matches_search() is False


def test_matches_local_area_accepts_sacramento_metro():
    job = Job(
        source="kaiser", title="RN", company="Kaiser",
        location="Roseville, CA, Onsite, Full-time",
        url="https://x/a",
    )
    assert job.matches_local_area() is True


def test_matches_local_area_rejects_pasadena():
    job = Job(
        source="kaiser", title="RN", company="Kaiser",
        location="Pasadena, CA, Flexible, Full-time",
        url="https://x/b",
    )
    assert job.matches_local_area() is False


def test_matches_local_area_rejects_washington_dc():
    job = Job(
        source="kaiser", title="RN", company="Kaiser",
        location="Washington D.C., DC", url="https://x/c",
    )
    assert job.matches_local_area() is False


def test_posted_at_rfc2822_parses():
    job = Job(
        source="x", title="RN", company="y", location="Roseville, CA",
        url="https://x/p1", posted_at="Mon, 13 Apr 2026 10:00:00 GMT",
    )
    assert job.posted_at_dt is not None
    assert job.posted_at_dt.year == 2026


def test_is_today_true_for_recent_post():
    now = datetime.now(timezone.utc)
    job = Job(
        source="x", title="RN", company="y", location="Roseville, CA",
        url="https://x/p2", posted_at=now.strftime("%a, %d %b %Y %H:%M:%S GMT"),
    )
    assert job.is_today() is True


def test_is_today_false_for_old_post():
    old = datetime.now(timezone.utc) - timedelta(days=3)
    job = Job(
        source="x", title="RN", company="y", location="Roseville, CA",
        url="https://x/p3", posted_at=old.strftime("%a, %d %b %Y %H:%M:%S GMT"),
    )
    assert job.is_today() is False


def test_is_today_false_when_no_date():
    job = Job(source="x", title="RN", company="y", location="Roseville", url="https://x/p4")
    assert job.is_today() is False
