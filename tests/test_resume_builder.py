import json

import pytest

from backend.ai.resume_builder import apply_patches, build_docx, build_pdf
from backend.ai.tailor import ResumePatch


@pytest.fixture
def resume():
    return {
        "name": "Hanna Safronova, RN",
        "location": "Roseville, CA",
        "licenses": ["CA RN #95452319", "BLS-AHA"],
        "target_roles": ["Registered Nurse", "Med-Surg RN", "Neurology RN"],
        "keywords": ["patient assessment", "telemetry monitoring", "IV"],
        "experience": [
            {"title": "Clinical Intern", "org": "Kharkiv Hospital", "dates": "2020-2022"},
        ],
        "education": ["BSN — In Progress"],
    }


def test_apply_patches_replaces_matching_path(resume):
    patches = [ResumePatch(
        path="/target_roles/0",
        original="Registered Nurse",
        replacement="Registered Nurse – Telemetry",
        reason="match posting language",
    )]
    out = apply_patches(resume, patches)
    assert out["target_roles"][0] == "Registered Nurse – Telemetry"
    # Original untouched
    assert resume["target_roles"][0] == "Registered Nurse"


def test_apply_patches_skips_on_original_mismatch(resume):
    patches = [ResumePatch(
        path="/target_roles/0",
        original="wrong original",
        replacement="Something else",
        reason="x",
    )]
    out = apply_patches(resume, patches)
    assert out["target_roles"][0] == "Registered Nurse"


def test_apply_patches_skips_invalid_path(resume):
    patches = [ResumePatch(
        path="/does/not/exist",
        original="x",
        replacement="y",
        reason="x",
    )]
    out = apply_patches(resume, patches)
    assert out == resume


def test_apply_patches_into_nested_experience(resume):
    patches = [ResumePatch(
        path="/experience/0/title",
        original="Clinical Intern",
        replacement="Clinical Intern (Neurology)",
        reason="emphasize neurology",
    )]
    out = apply_patches(resume, patches)
    assert out["experience"][0]["title"] == "Clinical Intern (Neurology)"


def test_build_pdf_produces_pdf_bytes(resume):
    data = build_pdf(resume)
    assert data.startswith(b"%PDF-")
    assert len(data) > 500


def test_build_docx_produces_valid_zip(resume):
    data = build_docx(resume)
    # DOCX files are ZIP archives starting with PK
    assert data[:2] == b"PK"
    assert len(data) > 500


def test_build_pdf_handles_real_resume_json():
    from backend.ai.scorer import load_resume
    resume = load_resume()
    pdf = build_pdf(resume)
    assert pdf.startswith(b"%PDF-")
