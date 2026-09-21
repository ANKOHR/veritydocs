from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TESSERACT_ROOT = Path("C:/Program Files/Tesseract-OCR")
if (TESSERACT_ROOT / "tesseract.exe").is_file():
    os.environ["PATH"] = f"{TESSERACT_ROOT};{os.environ.get('PATH', '')}"


def _run_fixture(client, fixture_name: str):
    case = client.post("/api/cases", json={"name": f"Demo test {fixture_name}"})
    assert case.status_code == 201
    case_id = case.json()["id"]
    payload = {
        "file": (
            fixture_name,
            BytesIO((REPOSITORY_ROOT / "fixtures" / fixture_name).read_bytes()),
            "application/pdf",
        )
    }
    uploaded = client.post(f"/api/cases/{case_id}/documents", files=payload)
    assert uploaded.status_code == 201
    return client.get(f"/api/cases/{case_id}").json()


def test_demo_page_exposes_upload_samples_and_footer(client):
    response = client.get("/demo")

    assert response.status_code == 200
    assert "Invoice PDF or image" in response.text
    assert "Clean sample" in response.text
    assert "Totals mismatch sample" in response.text
    assert "Missing field sample" in response.text
    assert 'href="https://github.com/ANKOHR/veritydocs"' in response.text
    assert "Demo of VerityDocs document validation" in response.text
    assert "—" not in response.text


@pytest.mark.skipif(
    not (TESSERACT_ROOT / "tesseract.exe").is_file(),
    reason="synthetic image-only invoice samples require the repository Tesseract runtime",
)
def test_demo_samples_preserve_clean_mismatch_and_missing_field_behaviour(client):
    clean = _run_fixture(client, "invoice_inv_0042_scan.pdf")
    clean_check = next(item for item in clean["validations"] if item["rule_id"] == "FIN-001")
    assert clean_check["status"] == "PASS"
    assert clean_check["expected"] == 9600.0
    assert clean_check["actual"] == 9600.0

    mismatch = _run_fixture(client, "invoice_inv_0042_inconsistent_scan.pdf")
    mismatch_check = next(
        item for item in mismatch["validations"] if item["rule_id"] == "FIN-001"
    )
    assert mismatch_check["status"] == "FAIL"
    assert mismatch_check["expected"] == 9600.0
    assert mismatch_check["actual"] == 9900.0

    missing = _run_fixture(client, "invoice_inv_0042_missing_tax_scan.pdf")
    missing_check = next(item for item in missing["validations"] if item["rule_id"] == "FIN-001")
    assert missing_check["status"] == "UNABLE_TO_VERIFY"
    assert "missing net, tax, or gross" in missing_check["message"]
