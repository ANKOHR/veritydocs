from __future__ import annotations

import io
from decimal import Decimal

import pymupdf as fitz
import pytest
from PIL import Image
from veritydocs_api.confidence import field_confidence, needs_review
from veritydocs_api.pipeline.normalize import normalize_csv, normalize_pdf
from veritydocs_api.pipeline.ocr import enrich_page_with_ocr
from veritydocs_api.pipeline.types import NormalizedPage, TextBlock
from veritydocs_api.providers import DemoExtractionProvider
from veritydocs_api.reconcile import DocumentFacts, reconcile_case
from veritydocs_api.schemas import (
    InvoiceExtraction,
    OperatingStatementExtraction,
    PropertyTaxExtraction,
    RentRollExtraction,
    UnitExtraction,
)
from veritydocs_api.storage import LocalObjectStore, S3ObjectStore, sha256_bytes
from veritydocs_api.validation import validate_document


def _pdf(text: str | None = None) -> bytes:
    document = fitz.open()
    if text is not None:
        page = document.new_page()
        page.insert_text((50, 50), text)
    data = document.tobytes()
    document.close()
    return data


def test_corrupt_pdf_fails_closed(tmp_path):
    with pytest.raises(fitz.FileDataError):
        normalize_pdf("bad", "bad.pdf", "application/pdf", b"not a PDF", LocalObjectStore(tmp_path))


def test_empty_pdf_fails_closed(tmp_path):
    with pytest.raises(fitz.EmptyFileError):
        normalize_pdf("empty", "empty.pdf", "application/pdf", b"", LocalObjectStore(tmp_path))


def test_unknown_extension_is_explicitly_unclassified(tmp_path):
    from veritydocs_api.pipeline.normalize import normalize_document

    normalized = normalize_document(
        "unknown", "notes.bin", "application/octet-stream", b"x", LocalObjectStore(tmp_path)
    )
    assert normalized.metadata["format"] == "unknown"
    assert normalized.pages[0].text == "Unknown document format"


def test_csv_rows_are_normalized_into_a_table():
    normalized = normalize_csv("csv", "ledger.csv", "text/csv", b"Name,Amount\nA,10\nB,20\n")
    assert normalized.pages[0].tables[0].headers == ["Name", "Amount"]
    assert normalized.pages[0].tables[0].rows == [["A", "10"], ["B", "20"]]


def test_pdf_evidence_boxes_use_rendered_image_coordinates(tmp_path):
    normalized = normalize_pdf(
        "pdf",
        "source.pdf",
        "application/pdf",
        _pdf("Gross: GBP 9,600.00"),
        LocalObjectStore(tmp_path),
    )
    page = normalized.pages[0]
    evidence = normalized.find_evidence("Gross")
    assert page.width and page.height
    assert evidence and evidence["bbox"]
    assert evidence["bbox"][2] <= page.width
    assert evidence["bbox"][3] <= page.height


def test_ocr_tokens_retain_bounding_boxes_and_confidence():
    image = Image.new("RGB", (100, 50), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    class FakeEngine:
        def image_to_blocks(self, data: bytes):
            assert data.startswith(b"\x89PNG")
            return [TextBlock("Gross:", [1, 2, 20, 12], kind="ocr_token", confidence=0.91)], 0.91

    page = NormalizedPage(1, width=100, height=50)
    enriched = enrich_page_with_ocr(page, buffer.getvalue(), FakeEngine())
    assert enriched.ocr_used is True
    assert enriched.ocr_confidence == 0.91
    assert enriched.blocks[0].bbox == [1, 2, 20, 12]
    assert enriched.text == "Gross:"


def test_demo_provider_classifies_ocr_invoice():
    page = NormalizedPage(
        1,
        blocks=[
            TextBlock("INVOICE", kind="ocr_token"),
            TextBlock("VAT:", kind="ocr_token"),
            TextBlock("1,600.00", kind="ocr_token"),
        ],
    )
    result = DemoExtractionProvider().classify(
        type("Document", (), {"filename": "scan.pdf", "text": page.text})()
    )
    assert result.document_type == "invoice"


def test_demo_provider_extracts_invoice_from_spaced_ocr_text():
    from veritydocs_api.pipeline.types import NormalizedDocument

    document = NormalizedDocument(
        "invoice",
        "invoice_inv_0042_scan.pdf",
        "application/pdf",
        [
            NormalizedPage(
                1,
                blocks=[
                    TextBlock("INVOICE", kind="ocr_token"),
                    TextBlock("Invoice", kind="ocr_token"),
                    TextBlock("number:", kind="ocr_token"),
                    TextBlock("INV-0042", kind="ocr_token"),
                    TextBlock("Net:", kind="ocr_token"),
                    TextBlock("GBP", kind="ocr_token"),
                    TextBlock("8,000.00", kind="ocr_token"),
                    TextBlock("VAT:", kind="ocr_token"),
                    TextBlock("GBP", kind="ocr_token"),
                    TextBlock("1,600.00", kind="ocr_token"),
                    TextBlock("Gross:", kind="ocr_token"),
                    TextBlock("GBP", kind="ocr_token"),
                    TextBlock("9,600.00", kind="ocr_token"),
                ],
                ocr_confidence=0.91,
            )
        ],
    )
    result = DemoExtractionProvider().extract("invoice", document)
    assert result.model.net == Decimal("8000.00")
    assert result.model.tax == Decimal("1600.00")
    assert result.model.gross == Decimal("9600.00")
    assert result.model.invoice_number == "INV-0042"


@pytest.mark.parametrize(
    ("net", "tax", "gross", "expected"),
    [
        (Decimal(8000), Decimal(1600), Decimal(9600), "PASS"),
        (Decimal(8000), Decimal(1600), Decimal(9900), "FAIL"),
        (Decimal(8000), None, Decimal(9600), "UNABLE_TO_VERIFY"),
    ],
)
def test_invoice_rule_has_explicit_status(net, tax, gross, expected):
    outcomes = validate_document("invoice", InvoiceExtraction(net=net, tax=tax, gross=gross))
    assert outcomes[0].status == expected


def test_rent_roll_rule_catches_row_count_mismatch():
    model = RentRollExtraction(
        units=[UnitExtraction(unit_id="1A", monthly_rent=Decimal(100))], total_units=2
    )
    outcomes = validate_document("rent_roll", model)
    assert next(item for item in outcomes if item.rule_id == "RR-004").status == "FAIL"


def test_operating_statement_rule_catches_wrong_noi():
    model = OperatingStatementExtraction(
        annual_revenue=Decimal(100), operating_expenses=Decimal(20), annual_noi=Decimal(90)
    )
    assert validate_document("operating_statement", model)[0].status == "FAIL"


def test_tax_rule_returns_unable_to_verify_for_missing_value():
    assert validate_document("tax_record", PropertyTaxExtraction())[0].status == "UNABLE_TO_VERIFY"


def test_reconciliation_surfaces_rent_conflict():
    left = RentRollExtraction(reported_monthly_rent=Decimal(8000))
    right = OperatingStatementExtraction(rental_income=Decimal(8100))
    result = reconcile_case(
        [
            DocumentFacts("rent", "rent_roll", left),
            DocumentFacts("ops", "operating_statement", right),
        ]
    )
    rent = next(item for item in result if item.metric == "monthly_rent")
    assert rent.status == "CONFLICT"
    assert rent.difference == -100.0


def test_reconciliation_surfaces_address_conflict():
    first = OperatingStatementExtraction(property_address="1 High Street")
    second = PropertyTaxExtraction(property_address="2 Low Street")
    result = reconcile_case(
        [
            DocumentFacts("one", "operating_statement", first),
            DocumentFacts("two", "tax_record", second),
        ]
    )
    assert next(item for item in result if item.metric == "property_address").status == "CONFLICT"


def test_reconciliation_can_return_unable_to_verify():
    result = reconcile_case([DocumentFacts("rent", "rent_roll", RentRollExtraction())])
    assert (
        next(item for item in result if item.metric == "monthly_rent").status == "UNABLE_TO_VERIFY"
    )


def test_confidence_penalizes_failed_validation():
    passing = field_confidence(0.96, 0.95, ["PASS"])
    failing = field_confidence(0.96, 0.95, ["FAIL"])
    assert failing < passing


def test_missing_or_conflicted_field_requires_review():
    assert needs_review(0.9, [], value_is_missing=True)
    assert needs_review(0.9, ["CONFLICT"])
    assert not needs_review(0.9, ["PASS"])


def test_local_store_round_trips_json(tmp_path):
    store = LocalObjectStore(tmp_path)
    store.put_json("nested/value.json", {"status": "verified"})
    assert b'"status": "verified"' in store.get_bytes("nested/value.json")
    assert store.exists("nested/value.json")


def test_s3_store_requires_all_deployment_credentials():
    with pytest.raises(RuntimeError, match="missing"):
        S3ObjectStore(None, None, None, None, "ams")


def test_hash_is_stable_and_sha256_length_is_fixed():
    digest = sha256_bytes(b"same bytes")
    assert digest == sha256_bytes(b"same bytes")
    assert len(digest) == 64


def test_generated_scan_fixture_is_image_only():
    fixture = fitz.open("fixtures/invoice_inv_0042_scan.pdf")
    assert fixture.page_count == 1
    assert fixture[0].get_text().strip() == ""
    fixture.close()
