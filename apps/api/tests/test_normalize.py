from __future__ import annotations

from veritydocs_api.pipeline.normalize import normalize_xlsx
from veritydocs_api.seed import build_rent_roll
from veritydocs_api.storage import LocalObjectStore


def test_xlsx_header_offset_and_totals_are_normalized(tmp_path):
    normalized = normalize_xlsx(
        "doc_test",
        "rent_roll.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        build_rent_roll(),
    )
    table = normalized.pages[0].tables[0]
    assert table.headers == ["Unit", "Status", "Monthly Rent", "Lease End"]
    assert len(table.rows) == 48
    assert table.source_range == "September Rent Roll!row-13"
    assert "Reported monthly rent" in normalized.text


def test_pdf_pages_keep_rendered_artifact_and_source_blocks(tmp_path):
    import pymupdf as fitz

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((50, 50), "Loan balance: £4,180,000")
    data = pdf.tobytes()
    pdf.close()
    store = LocalObjectStore(tmp_path / "objects")
    from veritydocs_api.pipeline.normalize import normalize_pdf

    normalized = normalize_pdf("doc_pdf", "loan.pdf", "application/pdf", data, store)
    assert normalized.pages[0].image_key
    assert store.exists(normalized.pages[0].image_key)
    assert normalized.find_evidence("£4,180,000")["page"] == 1
