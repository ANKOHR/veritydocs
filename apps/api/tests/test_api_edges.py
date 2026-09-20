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


def _case(client, name="Case", tenant="demo-tenant"):
    return client.post("/api/cases", json={"name": name}, headers={"X-Tenant-ID": tenant}).json()


def _upload(
    client,
    case_id,
    filename="invoice.pdf",
    text="Invoice Net £100 VAT £20 Gross £120",
    tenant="demo-tenant",
):
    return client.post(
        f"/api/cases/{case_id}/documents",
        files={"file": (filename, BytesIO(_pdf(text)), "application/pdf")},
        headers={"X-Tenant-ID": tenant},
    )


def test_upload_rejects_unsupported_extension(client):
    case_id = _case(client)["id"]
    response = client.post(
        f"/api/cases/{case_id}/documents",
        files={"file": ("malware.exe", BytesIO(b"x"), "application/octet-stream")},
    )
    assert response.status_code == 415


def test_upload_rejects_empty_file(client):
    case_id = _case(client)["id"]
    response = client.post(
        f"/api/cases/{case_id}/documents",
        files={"file": ("empty.pdf", BytesIO(b""), "application/pdf")},
    )
    assert response.status_code == 400


def test_processing_endpoint_exposes_artifacts_and_audit(client):
    case_id = _case(client)["id"]
    uploaded = _upload(client, case_id)
    assert uploaded.status_code == 201
    document_id = uploaded.json()["document_id"]
    processing = client.get(f"/api/documents/{document_id}/processing")
    assert processing.status_code == 200
    body = processing.json()
    assert body["status"] == "complete"
    assert {item["kind"] for item in body["artifacts"]} >= {"normalized", "extraction"}
    assert any(item["event_type"] == "document.processed" for item in body["audit_events"])


def test_normalized_artifact_is_retrievable_as_json(client):
    case_id = _case(client)["id"]
    document_id = _upload(client, case_id).json()["document_id"]
    response = client.get(f"/api/documents/{document_id}/artifacts/normalized")
    assert response.status_code == 200
    assert response.json()["pages"][0]["blocks"]


def test_original_document_content_is_retrievable(client):
    case_id = _case(client)["id"]
    document_id = _upload(client, case_id).json()["document_id"]
    response = client.get(f"/api/documents/{document_id}/content")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


def test_rendered_page_is_retrievable(client):
    case_id = _case(client)["id"]
    document_id = _upload(client, case_id).json()["document_id"]
    response = client.get(f"/api/documents/{document_id}/pages/1")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")


def test_document_content_is_tenant_isolated(client):
    case_id = _case(client, tenant="tenant-a")["id"]
    document_id = _upload(client, case_id, tenant="tenant-a").json()["document_id"]
    assert (
        client.get(
            f"/api/documents/{document_id}/content", headers={"X-Tenant-ID": "tenant-b"}
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/documents/{document_id}/processing", headers={"X-Tenant-ID": "tenant-b"}
        ).status_code
        == 404
    )


def test_artifact_is_tenant_isolated(client):
    case_id = _case(client, tenant="tenant-a")["id"]
    document_id = _upload(client, case_id, tenant="tenant-a").json()["document_id"]
    response = client.get(
        f"/api/documents/{document_id}/artifacts/normalized", headers={"X-Tenant-ID": "tenant-b"}
    )
    assert response.status_code == 404


def test_same_content_with_different_filename_is_duplicate(client):
    case_id = _case(client)["id"]
    data = _pdf("Invoice Net £100 VAT £20 Gross £120")
    first = client.post(
        f"/api/cases/{case_id}/documents",
        files={"file": ("first.pdf", BytesIO(data), "application/pdf")},
    )
    second = client.post(
        f"/api/cases/{case_id}/documents",
        files={"file": ("renamed.pdf", BytesIO(data), "application/pdf")},
    )
    assert first.status_code == second.status_code == 201
    assert second.json()["duplicate"] is True
    assert second.json()["document_id"] == first.json()["document_id"]


def test_different_content_is_not_duplicate(client):
    case_id = _case(client)["id"]
    first = _upload(client, case_id, text="Invoice Net £100 VAT £20 Gross £120")
    second = _upload(client, case_id, "second.pdf", text="Invoice Net £200 VAT £40 Gross £240")
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is False
    assert second.json()["document_id"] != first.json()["document_id"]


def test_invalid_case_is_not_leaked(client):
    response = client.post(
        "/api/cases/not-a-real-case/documents",
        files={"file": ("a.pdf", BytesIO(_pdf("Invoice")), "application/pdf")},
    )
    assert response.status_code == 404


def test_case_list_is_tenant_scoped(client):
    _case(client, "Visible", "tenant-a")
    _case(client, "Hidden", "tenant-b")
    names = {
        item["name"]
        for item in client.get("/api/cases", headers={"X-Tenant-ID": "tenant-a"}).json()
    }
    assert names == {"Visible"}


def test_missing_review_returns_404(client):
    response = client.post(
        "/api/review/not-a-review/resolve",
        json={"decision": "approve", "reviewer": "qa"},
    )
    assert response.status_code == 404


def test_evaluation_summary_is_explicitly_fixture_only(client):
    body = client.get("/api/evaluations/summary").json()
    assert body["status"] == "fixture_only"
    assert body["dataset"] == "synthetic"
    assert body["held_out"] is False


def test_contract_seed_cannot_cross_tenant_boundary(client):
    case_id = _case(client, tenant="tenant-a")["id"]
    response = client.post(
        f"/api/cases/{case_id}/contract-seed", headers={"X-Tenant-ID": "tenant-b"}
    )
    assert response.status_code == 404
