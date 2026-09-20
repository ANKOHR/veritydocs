from __future__ import annotations

from io import BytesIO

import pymupdf as fitz


def _pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((50, 50), text)
    data = document.tobytes()
    document.close()
    return data


def test_demo_case_exposes_provenance_reconciliation_and_review(client):
    created = client.post(
        "/api/cases",
        json={"name": "Acme Property Acquisition", "property_address": "32 New Street, London"},
    )
    assert created.status_code == 201
    case_id = created.json()["id"]
    response = client.post(f"/api/cases/{case_id}/demo-seed")
    assert response.status_code == 200
    body = response.json()
    assert len(body["documents"]) == 4
    assert any(item["status"] == "CONFLICT" for item in body["reconciliations"])
    assert len([item for item in body["reviews"] if item["status"] == "open"]) == 2
    loan = next(
        field
        for doc in body["documents"]
        for field in doc["fields"]
        if field["field_name"] == "loan_balance"
    )
    assert loan["evidence"]
    assert loan["evidence"][0]["page"] == 1


def test_duplicate_upload_is_idempotent_and_tenant_isolation_holds(client):
    created = client.post(
        "/api/cases", json={"name": "Upload test"}, headers={"X-Tenant-ID": "tenant-a"}
    )
    case_id = created.json()["id"]
    payload = {
        "file": (
            "invoice.pdf",
            BytesIO(_pdf("Invoice Supplier: Example Net £100 VAT £20 Gross £120")),
            "application/pdf",
        )
    }
    first = client.post(
        f"/api/cases/{case_id}/documents", files=payload, headers={"X-Tenant-ID": "tenant-a"}
    )
    second = client.post(
        f"/api/cases/{case_id}/documents", files=payload, headers={"X-Tenant-ID": "tenant-a"}
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["duplicate"] is True
    hidden = client.get(f"/api/cases/{case_id}", headers={"X-Tenant-ID": "tenant-b"})
    assert hidden.status_code == 404


def test_review_resolution_records_human_value(client):
    created = client.post("/api/cases", json={"name": "Review test"})
    case_id = created.json()["id"]
    seeded = client.post(f"/api/cases/{case_id}/demo-seed").json()
    review = next(item for item in seeded["reviews"] if item["status"] == "open")
    resolved = client.post(
        f"/api/review/{review['id']}/resolve",
        json={
            "decision": "unable_to_verify",
            "reviewer": "qa",
            "reason": "Source does not support a verified value.",
        },
    )
    assert resolved.status_code == 200
    assert any(
        item["id"] == review["id"] and item["status"] == "resolved"
        for item in resolved.json()["reviews"]
    )


def test_contract_payment_fixture_surfaces_value_conflict(client):
    created = client.post("/api/cases", json={"name": "Riverside Contract Review"})
    case_id = created.json()["id"]
    seeded = client.post(f"/api/cases/{case_id}/contract-seed")
    assert seeded.status_code == 200
    body = seeded.json()
    assert {document["document_type"] for document in body["documents"]} == {
        "contract",
        "payment_application",
    }
    conflict = next(
        item
        for item in body["reconciliations"]
        if item["metric"] == "payment_against_contract_value"
    )
    assert conflict["status"] == "CONFLICT"
