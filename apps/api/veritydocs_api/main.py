from __future__ import annotations

import mimetypes
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db, init_db
from .models import AuditEventModel, CaseModel, DocumentModel, ExtractedFieldModel, ReviewItemModel
from .schemas import CaseView, ReviewDecision
from .seed import seed_acme_case, seed_contract_case
from .service import case_view, object_store, process_document
from .storage import sha256_bytes


class CreateCaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    property_address: str | None = None


class CaseListItem(BaseModel):
    id: str
    name: str
    property_address: str | None
    status: str
    document_count: int
    exception_count: int
    overall_confidence: float


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    duplicate: bool = False
    status: str


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    object_store()
    yield


app = FastAPI(
    title="VerityDocs API",
    version="0.1.0",
    description="Evidence-backed document intelligence and reconciliation API.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _tenant(header: str | None) -> str:
    return header or "demo-tenant"


def _owned_case(db: Session, case_id: str, tenant_id: str) -> CaseModel:
    case = db.scalar(
        select(CaseModel).where(CaseModel.id == case_id, CaseModel.tenant_id == tenant_id)
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _owned_document(db: Session, document_id: str, tenant_id: str) -> DocumentModel:
    document = db.get(DocumentModel, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    _owned_case(db, document.case_id, tenant_id)
    return document


def _process_in_background(document_id: str) -> None:
    from .database import SessionLocal

    db = SessionLocal()
    try:
        process_document(db, document_id)
    finally:
        db.close()


@app.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "service": "veritydocs-api", "environment": settings.app_env}


@app.post("/api/cases", response_model=CaseView, status_code=201)
def create_case(
    payload: CreateCaseRequest,
    db: Session = Depends(get_db),
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> CaseView:
    case = CaseModel(
        name=payload.name,
        property_address=payload.property_address,
        tenant_id=_tenant(tenant_id),
        status="empty",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case_view(db, case.id)


@app.get("/api/cases", response_model=list[CaseListItem])
def list_cases(
    db: Session = Depends(get_db),
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> list[CaseListItem]:
    cases = list(
        db.scalars(
            select(CaseModel)
            .where(CaseModel.tenant_id == _tenant(tenant_id))
            .order_by(CaseModel.updated_at.desc())
        )
    )
    result: list[CaseListItem] = []
    for case in cases:
        view = case_view(db, case.id)
        result.append(
            CaseListItem(
                id=case.id,
                name=case.name,
                property_address=case.property_address,
                status=case.status,
                document_count=len(view.documents),
                exception_count=view.exception_count,
                overall_confidence=view.overall_confidence,
            )
        )
    return result


@app.get("/api/cases/{case_id}", response_model=CaseView)
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> CaseView:
    _owned_case(db, case_id, _tenant(tenant_id))
    return case_view(db, case_id)


@app.post("/api/cases/{case_id}/demo-seed", response_model=CaseView)
def demo_seed(
    case_id: str | None = None,
    db: Session = Depends(get_db),
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> CaseView:
    if case_id:
        _owned_case(db, case_id, _tenant(tenant_id))
    case = seed_acme_case(db, case_id=case_id)
    if case.tenant_id != _tenant(tenant_id):
        raise HTTPException(status_code=403, detail="Tenant boundary violation")
    return case_view(db, case.id)


@app.post("/api/cases/{case_id}/contract-seed", response_model=CaseView)
def contract_seed(
    case_id: str,
    db: Session = Depends(get_db),
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> CaseView:
    _owned_case(db, case_id, _tenant(tenant_id))
    case = seed_contract_case(db, case_id=case_id)
    return case_view(db, case.id)


@app.post("/api/cases/{case_id}/documents", response_model=UploadResponse, status_code=201)
async def upload_document(
    case_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    run_pipeline: bool = Query(
        True, description="Process synchronously for demo use; disable for queued work."
    ),
    db: Session = Depends(get_db),
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> UploadResponse:
    case = _owned_case(db, case_id, _tenant(tenant_id))
    filename = Path(file.filename or "upload.bin").name
    extension = Path(filename).suffix.lower()
    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".xlsx", ".xlsm", ".csv"}
    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=415, detail="Supported types: PDF, PNG/JPEG, XLSX/XLSM and CSV"
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded document is empty")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Maximum document size is 25 MiB")
    digest = sha256_bytes(data)
    duplicate = db.scalar(
        select(DocumentModel).where(
            DocumentModel.case_id == case.id, DocumentModel.sha256 == digest
        )
    )
    if duplicate:
        return UploadResponse(
            document_id=duplicate.id,
            filename=duplicate.filename,
            duplicate=True,
            status=duplicate.status,
        )
    mime_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    key = f"documents/{case.id}/original/{filename}"
    object_store().put_bytes(key, data)
    document = DocumentModel(
        case_id=case.id,
        filename=filename,
        sha256=digest,
        mime_type=mime_type,
        size_bytes=len(data),
        storage_key=key,
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    if run_pipeline:
        process_document(db, document.id)
    else:
        settings = get_settings()
        if settings.redis_url:
            from .jobs import enqueue_document

            enqueue_document(document.id)
        else:
            background_tasks.add_task(_process_in_background, document.id)
    return UploadResponse(document_id=document.id, filename=filename, status=document.status)


@app.get("/api/documents/{document_id}/content")
def document_content(
    document_id: str,
    db: Session = Depends(get_db),
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> FileResponse:
    document = _owned_document(db, document_id, _tenant(tenant_id))
    path = Path(get_settings().storage_root) / document.storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Source artifact not found")
    return FileResponse(path, media_type=document.mime_type, filename=document.filename)


@app.get("/api/documents/{document_id}/pages/{page_number}")
def document_page(
    document_id: str,
    page_number: int,
    db: Session = Depends(get_db),
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> FileResponse:
    document = _owned_document(db, document_id, _tenant(tenant_id))
    if page_number < 1:
        raise HTTPException(status_code=400, detail="Page number must be positive")
    key = f"documents/{document.id}/rendered/page-{page_number:03d}.png"
    path = Path(get_settings().storage_root) / key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Rendered page artifact not found")
    return FileResponse(
        path, media_type="image/png", filename=f"{document.filename}-page-{page_number}.png"
    )


@app.get("/api/review", response_model=list[dict[str, object]])
def review_queue(
    db: Session = Depends(get_db),
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
    status: str = "open",
) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(ReviewItemModel)
            .join(CaseModel, CaseModel.id == ReviewItemModel.case_id)
            .where(CaseModel.tenant_id == _tenant(tenant_id), ReviewItemModel.status == status)
            .order_by(ReviewItemModel.created_at.desc())
        )
    )
    return [
        {
            "id": row.id,
            "case_id": row.case_id,
            "document_id": row.document_id,
            "field_id": row.field_id,
            "status": row.status,
            "reason": row.reason,
            "model_value": row.model_value_json,
            "human_value": row.human_value_json,
            "reviewer": row.reviewer,
        }
        for row in rows
    ]


@app.post("/api/review/{review_id}/resolve", response_model=CaseView)
def resolve_review(
    review_id: str,
    decision: ReviewDecision,
    db: Session = Depends(get_db),
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> CaseView:
    review = db.get(ReviewItemModel, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    case = _owned_case(db, review.case_id, _tenant(tenant_id))
    accepted = decision.decision.lower() in {"approve", "accept", "verify", "resolved"}
    review.status = "resolved"
    review.reviewer = decision.reviewer
    review.human_value_json = (
        decision.value if decision.value is not None else review.model_value_json
    )
    review.resolved_at = datetime.now(UTC)
    if review.field_id:
        field = db.get(ExtractedFieldModel, review.field_id)
        if field:
            if accepted and decision.value is not None:
                field.value_json = decision.value
                field.value_text = str(decision.value)
            field.status = "reviewed" if accepted else "unable_to_verify"
            field.validation_status = "HUMAN_VERIFIED" if accepted else "UNABLE_TO_VERIFY"
            field.warnings_json = [decision.reason] if decision.reason else []
    db.add(
        AuditEventModel(
            case_id=case.id,
            event_type="review.resolved",
            entity_type="review",
            entity_id=review.id,
            payload_json={"decision": decision.decision, "reviewer": decision.reviewer},
        )
    )
    db.commit()
    return case_view(db, case.id)


@app.get("/api/evaluations/summary")
def evaluation_summary() -> dict[str, object]:
    return {
        "status": "fixture_only",
        "dataset": "synthetic",
        "held_out": False,
        "message": "Run the local evaluation command to generate measured fixture metrics; no real-world accuracy is claimed.",
        "metrics": {},
    }
