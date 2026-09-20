from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def now() -> datetime:
    return datetime.now(UTC)


class CaseModel(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: uid("case"))
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, default="demo-tenant")
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    property_address: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(40), default="processing")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class DocumentModel(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("case_id", "sha256", name="uq_document_case_hash"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: uid("doc"))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    document_type: Mapped[str] = mapped_column(String(80), default="unknown")
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), default="uploaded")
    processing_version: Mapped[str] = mapped_column(String(120), default="veritydocs-pipeline-0.1")
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ArtifactModel(Base):
    __tablename__ = "document_artifacts"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: uid("art"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProcessingRunModel(Base):
    __tablename__ = "processing_runs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: uid("run"))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="running")
    current_stage: Mapped[str] = mapped_column(String(80), default="upload")
    pipeline_version: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), default="demo")
    model: Mapped[str | None] = mapped_column(String(120))
    timings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExtractedFieldModel(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: uid("field"))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(180), index=True)
    value_json: Mapped[object | None] = mapped_column(JSON)
    value_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    extraction_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    validation_status: Mapped[str] = mapped_column(String(40), default="not_checked")
    status: Mapped[str] = mapped_column(String(40), default="accepted")
    method: Mapped[str] = mapped_column(String(120), nullable=False)
    warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EvidenceModel(Base):
    __tablename__ = "field_evidence"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: uid("ev"))
    field_id: Mapped[str] = mapped_column(ForeignKey("extracted_fields.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text, default="")
    bbox_json: Mapped[list[float] | None] = mapped_column(JSON)
    section: Mapped[str | None] = mapped_column(String(240))
    artifact_key: Mapped[str | None] = mapped_column(String(500))


class ValidationResultModel(Base):
    __tablename__ = "validation_results"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: uid("val"))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    expected_json: Mapped[object | None] = mapped_column(JSON)
    actual_json: Mapped[object | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReconciliationModel(Base):
    __tablename__ = "reconciliations"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: uid("rec"))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    metric: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    left_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    right_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    left_value_json: Mapped[object | None] = mapped_column(JSON)
    right_value_json: Mapped[object | None] = mapped_column(JSON)
    difference: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReviewItemModel(Base):
    __tablename__ = "review_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: uid("review"))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    field_id: Mapped[str | None] = mapped_column(ForeignKey("extracted_fields.id"))
    status: Mapped[str] = mapped_column(String(40), default="open")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    model_value_json: Mapped[object | None] = mapped_column(JSON)
    human_value_json: Mapped[object | None] = mapped_column(JSON)
    reviewer: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: uid("audit"))
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
