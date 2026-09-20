from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .confidence import field_confidence
from .config import Settings, get_settings
from .models import (
    ArtifactModel,
    AuditEventModel,
    CaseModel,
    DocumentModel,
    EvidenceModel,
    ExtractedFieldModel,
    ProcessingRunModel,
    ReconciliationModel,
    ReviewItemModel,
    ValidationResultModel,
)
from .pipeline.normalize import normalize_document
from .pipeline.ocr import OCRUnavailable, TesseractOCREngine, enrich_page_with_ocr
from .pipeline.types import NormalizedDocument, TextBlock
from .providers import (
    EXTRACTION_SCHEMAS,
    DemoExtractionProvider,
    ExtractionProvider,
    OpenAIMultimodalProvider,
)
from .reconcile import DocumentFacts, reconcile_case
from .schemas import (
    CaseView,
    DocumentView,
    EvidenceRef,
    FieldView,
    ReconciliationView,
    ReviewView,
    ValidationView,
)
from .storage import LocalObjectStore, ObjectStore, S3ObjectStore, sha256_bytes
from .validation import ValidationOutcome, validate_document


def jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if hasattr(value, "isoformat") and not isinstance(value, (str, bytes)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


logger = logging.getLogger(__name__)


def object_store(settings: Settings | None = None) -> ObjectStore:
    selected = settings or get_settings()
    if selected.storage_backend.lower() == "s3":
        return S3ObjectStore(
            endpoint_url=selected.s3_endpoint_url,
            bucket=selected.s3_bucket,
            access_key_id=selected.s3_access_key_id,
            secret_access_key=selected.s3_secret_access_key,
            region=selected.s3_region,
            addressing_style=selected.s3_addressing_style,
        )
    return LocalObjectStore(selected.storage_root)


def _provider(settings: Settings) -> ExtractionProvider:
    if settings.extraction_provider.lower() == "openai":
        return OpenAIMultimodalProvider(settings)
    return DemoExtractionProvider()


def _evidence_needles(field_name: str, value: Any) -> list[str]:
    label = field_name.replace("_", " ")
    needles: list[str] = []
    if value is None:
        return [label]
    if isinstance(value, list):
        for item in value[:3]:
            if isinstance(item, dict):
                needles.extend(str(item_value) for item_value in item.values() if item_value)
    else:
        text = str(value)
        needles.append(text)
        try:
            number = Decimal(text.replace(",", ""))
            needles.extend([f"{number:,.2f}", f"{number:,.0f}", str(number)])
        except InvalidOperation:
            pass
    needles.append(label)
    return list(dict.fromkeys(needle for needle in needles if needle))


def _find_evidence(
    document: NormalizedDocument, field_name: str, value: Any
) -> dict[str, Any] | None:
    for needle in _evidence_needles(field_name, value):
        result = document.find_evidence(needle)
        if result:
            return result
    return None


def _delete_document_fields(db: Session, document_id: str) -> None:
    field_ids = list(
        db.scalars(
            select(ExtractedFieldModel.id).where(ExtractedFieldModel.document_id == document_id)
        )
    )
    if field_ids:
        db.execute(delete(EvidenceModel).where(EvidenceModel.field_id.in_(field_ids)))
        db.execute(
            delete(ReviewItemModel).where(
                ReviewItemModel.field_id.in_(field_ids), ReviewItemModel.status == "open"
            )
        )
    db.execute(delete(ExtractedFieldModel).where(ExtractedFieldModel.document_id == document_id))


def _write_artifact(
    db: Session,
    store: ObjectStore,
    document_id: str,
    kind: str,
    payload: Any,
) -> str:
    key = f"documents/{document_id}/{kind}.json"
    store.put_json(key, jsonable(payload))
    db.execute(
        delete(ArtifactModel).where(
            ArtifactModel.document_id == document_id,
            ArtifactModel.kind == kind,
        )
    )
    db.add(
        ArtifactModel(
            document_id=document_id,
            kind=kind,
            storage_key=key,
            sha256=sha256_bytes(json.dumps(jsonable(payload), sort_keys=True).encode("utf-8")),
            metadata_json={"kind": kind},
        )
    )
    return key


def _field_validation_status(field_name: str, outcomes: list[ValidationOutcome]) -> str:
    rules = {
        "gross": {"FIN-001"},
        "net": {"FIN-001"},
        "tax": {"FIN-001"},
        "total_units": {"RR-004"},
        "reported_monthly_rent": {"RR-007"},
        "annual_noi": {"OS-003"},
        "annual_revenue": {"OS-003"},
        "operating_expenses": {"OS-003"},
        "loan_balance": {"LOAN-001"},
        "interest_rate": {"LOAN-001"},
        "annual_property_tax": {"TAX-001"},
        "total_contract_value": {"CON-001"},
        "contract_reference": {"CON-001", "PAY-001"},
        "claimed_amount": {"PAY-001"},
    }
    relevant = [
        outcome.status for outcome in outcomes if outcome.rule_id in rules.get(field_name, set())
    ]
    if not relevant:
        return "NOT_CHECKED"
    if "FAIL" in relevant:
        return "FAIL"
    if "UNABLE_TO_VERIFY" in relevant:
        return "UNABLE_TO_VERIFY"
    return "PASS"


def _model_from_artifact(store: ObjectStore, document: DocumentModel) -> Any | None:
    schema = EXTRACTION_SCHEMAS.get(document.document_type)
    key = f"documents/{document.id}/extraction.json"
    if schema is None or not store.exists(key):
        return None
    try:
        return schema.model_validate(json.loads(store.get_bytes(key)))
    except (OSError, TypeError, ValueError, ValidationError):
        return None


def _field_for(db: Session, document_id: str, field_name: str) -> ExtractedFieldModel | None:
    return db.scalar(
        select(ExtractedFieldModel)
        .where(
            ExtractedFieldModel.document_id == document_id,
            ExtractedFieldModel.field_name == field_name,
        )
        .order_by(ExtractedFieldModel.created_at.desc())
    )


def _record_review(
    db: Session,
    case_id: str,
    document_id: str,
    reason: str,
    field_id: str | None = None,
    model_value: Any = None,
) -> None:
    existing = db.scalar(
        select(ReviewItemModel).where(
            ReviewItemModel.case_id == case_id,
            ReviewItemModel.document_id == document_id,
            ReviewItemModel.field_id == field_id,
            ReviewItemModel.reason == reason,
            ReviewItemModel.status == "open",
        )
    )
    if existing:
        return
    db.add(
        ReviewItemModel(
            case_id=case_id,
            document_id=document_id,
            field_id=field_id,
            reason=reason,
            model_value_json=jsonable(model_value),
        )
    )


def rebuild_case_derived(db: Session, case_id: str, store: ObjectStore) -> None:
    documents = list(db.scalars(select(DocumentModel).where(DocumentModel.case_id == case_id)))
    complete_documents = [document for document in documents if document.status == "complete"]
    db.execute(delete(ValidationResultModel).where(ValidationResultModel.case_id == case_id))
    db.execute(delete(ReconciliationModel).where(ReconciliationModel.case_id == case_id))
    db.execute(
        delete(ReviewItemModel).where(
            ReviewItemModel.case_id == case_id,
            ReviewItemModel.status == "open",
        )
    )

    facts: list[DocumentFacts] = []
    outcomes_by_document: dict[str, list[ValidationOutcome]] = {}
    for document in complete_documents:
        model = _model_from_artifact(store, document)
        if model is None:
            continue
        facts.append(DocumentFacts(document.id, document.document_type, model))
        outcomes = validate_document(document.document_type, model)
        outcomes_by_document[document.id] = outcomes
        for outcome in outcomes:
            db.add(
                ValidationResultModel(
                    case_id=case_id,
                    document_id=document.id,
                    rule_id=outcome.rule_id,
                    status=outcome.status,
                    message=outcome.message,
                    expected_json=jsonable(outcome.expected),
                    actual_json=jsonable(outcome.actual),
                )
            )
        for outcome in outcomes:
            if outcome.status == "FAIL":
                target_name = {
                    "FIN-001": "gross",
                    "RR-004": "total_units",
                    "RR-007": "reported_monthly_rent",
                    "OS-003": "annual_noi",
                }.get(outcome.rule_id)
                target = _field_for(db, document.id, target_name) if target_name else None
                _record_review(
                    db,
                    case_id,
                    document.id,
                    f"Validation {outcome.rule_id} failed: {outcome.message}",
                    target.id if target else None,
                    target.value_json if target else None,
                )

        # A missing lease end is a concrete reviewable exception, not a guessed value.
        if document.document_type == "rent_roll":
            missing = [
                unit.unit_id
                for unit in model.units
                if unit.status == "Occupied" and unit.lease_end is None
            ]
            if missing:
                units_field = _field_for(db, document.id, "units")
                _record_review(
                    db,
                    case_id,
                    document.id,
                    f"Lease-end date is missing for unit(s): {', '.join(missing[:8])}",
                    units_field.id if units_field else None,
                    units_field.value_json if units_field else None,
                )

    for outcome in reconcile_case(facts):
        db.add(
            ReconciliationModel(
                case_id=case_id,
                metric=outcome.metric,
                status=outcome.status,
                left_document_id=outcome.left_document_id,
                right_document_id=outcome.right_document_id,
                left_value_json=jsonable(outcome.left_value),
                right_value_json=jsonable(outcome.right_value),
                difference=outcome.difference,
                message=outcome.message,
            )
        )
        if outcome.status == "CONFLICT":
            target_document = outcome.right_document_id or outcome.left_document_id
            target_field_name = {
                "accounting_period": "accounting_period",
                "contract_reference": "contract_reference",
                "payment_against_contract_value": "claimed_amount",
            }.get(outcome.metric, "reported_monthly_rent")
            target = _field_for(db, target_document, target_field_name) if target_document else None
            _record_review(
                db,
                case_id,
                target_document or outcome.left_document_id or "unknown",
                f"Cross-document conflict for {outcome.metric}: {outcome.message}",
                target.id if target else None,
                target.value_json if target else None,
            )

    db.flush()
    case = db.get(CaseModel, case_id)
    if case:
        address = next(
            (
                getattr(f.model, "property_address", None)
                for f in facts
                if getattr(f.model, "property_address", None)
            ),
            None,
        )
        if address:
            case.property_address = address
        open_reviews = db.scalar(
            select(ReviewItemModel.id).where(
                ReviewItemModel.case_id == case_id,
                ReviewItemModel.status == "open",
            )
        )
        case.status = "review" if open_reviews else "complete"
        case.updated_at = datetime.now(UTC)


def process_document(
    db: Session,
    document_id: str,
    settings: Settings | None = None,
    store: ObjectStore | None = None,
) -> ProcessingRunModel:
    settings = settings or get_settings()
    store = store or object_store(settings)
    document = db.get(DocumentModel, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} was not found")
    case = db.get(CaseModel, document.case_id)
    if case is None:
        raise ValueError(f"Case {document.case_id} was not found")

    run = ProcessingRunModel(
        case_id=case.id,
        document_id=document.id,
        pipeline_version=settings.pipeline_version,
        status="running",
        current_stage="ingestion",
        provider=settings.extraction_provider,
        timings_json={},
    )
    db.add(run)
    document.status = "processing"
    case.status = "processing"
    db.flush()
    timings: dict[str, Any] = {}
    started = time.perf_counter()

    try:
        raw = store.get_bytes(document.storage_key)
        stage_started = time.perf_counter()
        normalized = normalize_document(
            document.id, document.filename, document.mime_type, raw, store
        )
        timings["normalize_ms"] = round((time.perf_counter() - stage_started) * 1000, 2)
        run.current_stage = "ocr"
        stage_started = time.perf_counter()
        ocr_engine = None
        if settings.ocr_engine.lower() == "tesseract":
            try:
                ocr_engine = TesseractOCREngine()
            except OCRUnavailable:
                # Native PDFs and spreadsheets remain processable; image-only inputs will
                # retain a low OCR score and be routed for review until the engine exists.
                ocr_engine = None
        if ocr_engine:
            for page in normalized.pages:
                if not page.text and page.image_key:
                    try:
                        enrich_page_with_ocr(page, store.get_bytes(page.image_key), ocr_engine)
                    except (OCRUnavailable, OSError, RuntimeError) as exc:
                        page.blocks.append(TextBlock("OCR unavailable: " + str(exc)))
        timings["ocr_ms"] = round((time.perf_counter() - stage_started) * 1000, 2)
        timings["ocr_engine"] = ocr_engine.name if ocr_engine else "unavailable"
        timings["ocr_version"] = getattr(ocr_engine, "version", None)
        timings["storage_backend"] = settings.storage_backend
        _write_artifact(db, store, document.id, "normalized", asdict(normalized))

        run.current_stage = "classification"
        provider = _provider(settings)
        run.provider = provider.name
        classification = provider.classify(normalized)
        document.document_type = classification.document_type
        document.classification_confidence = classification.confidence
        run.model = provider.model_name

        run.current_stage = "extraction"
        result = provider.extract(classification.document_type, normalized)
        _delete_document_fields(db, document.id)
        extraction_key = _write_artifact(
            db, store, document.id, "extraction", result.model.model_dump(mode="json")
        )
        document.page_count = len(normalized.pages)
        document.status = "complete"
        document.processing_version = settings.pipeline_version

        validation = validate_document(classification.document_type, result.model)
        field_values = result.model.model_dump(mode="json")
        for field_name, value in field_values.items():
            evidence = _find_evidence(normalized, field_name, value)
            relevant_statuses = [
                outcome.status
                for outcome in validation
                if outcome.rule_id
                in {
                    "FIN-001": {"gross", "net", "tax"},
                    "RR-004": {"total_units"},
                    "RR-007": {"reported_monthly_rent"},
                    "OS-003": {"annual_noi", "annual_revenue", "operating_expenses"},
                    "LOAN-001": {"loan_balance", "interest_rate"},
                    "TAX-001": {"annual_property_tax"},
                    "CON-001": {"total_contract_value", "contract_reference"},
                    "PAY-001": {"claimed_amount", "contract_reference"},
                }.get(field_name, set())
            ]
            score = field_confidence(
                result.extraction_confidence,
                normalized.average_ocr_confidence,
                relevant_statuses,
            )
            field = ExtractedFieldModel(
                case_id=case.id,
                document_id=document.id,
                field_name=field_name,
                value_json=jsonable(value),
                value_text=json.dumps(jsonable(value), ensure_ascii=False)
                if isinstance(value, (dict, list))
                else (None if value is None else str(value)),
                confidence=score,
                extraction_confidence=result.extraction_confidence,
                ocr_confidence=normalized.average_ocr_confidence,
                validation_status=_field_validation_status(field_name, validation),
                status="accepted" if value is not None else "missing",
                method=f"{result.provider}:{result.model_name}",
                warnings_json=[]
                if evidence
                else ["No exact source span matched; review recommended."],
            )
            db.add(field)
            db.flush()
            if evidence:
                db.add(
                    EvidenceModel(
                        field_id=field.id,
                        document_id=document.id,
                        page_number=evidence["page"],
                        text=evidence["text"],
                        bbox_json=evidence.get("bbox"),
                        section=evidence.get("section"),
                        artifact_key=evidence.get("artifact_key"),
                    )
                )
        run.current_stage = "validation"
        run.timings_json = timings
        rebuild_case_derived(db, case.id, store)
        run.current_stage = "completed"
        run.status = "complete"
        run.completed_at = datetime.now(UTC)
        timings["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
        run.timings_json = timings
        db.add(
            AuditEventModel(
                case_id=case.id,
                event_type="document.processed",
                entity_type="document",
                entity_id=document.id,
                payload_json={
                    "document_type": document.document_type,
                    "provider": provider.name,
                    "artifact": extraction_key,
                },
            )
        )
        db.commit()
        db.refresh(run)
        logger.info(
            "document_processed document_id=%s type=%s provider=%s ocr=%s ocr_version=%s",
            document.id,
            document.document_type,
            provider.name,
            timings["ocr_engine"],
            timings["ocr_version"],
        )
        return run
    except Exception as exc:
        db.rollback()
        document = db.get(DocumentModel, document_id)
        if document:
            document.status = "failed"
        failed_run = ProcessingRunModel(
            case_id=case.id,
            document_id=document_id,
            pipeline_version=settings.pipeline_version,
            provider=settings.extraction_provider,
            status="failed",
            current_stage="failed",
            error=f"{type(exc).__name__}: {exc}",
            timings_json=timings,
            completed_at=datetime.now(UTC),
        )
        db.add(failed_run)
        db.commit()
        raise


def _evidence_views(db: Session, field_id: str) -> list[EvidenceRef]:
    rows = list(db.scalars(select(EvidenceModel).where(EvidenceModel.field_id == field_id)))
    return [
        EvidenceRef(
            document_id=row.document_id,
            page=row.page_number,
            text=row.text,
            bbox=row.bbox_json,
            section=row.section,
            artifact_key=row.artifact_key,
        )
        for row in rows
    ]


def case_view(db: Session, case_id: str) -> CaseView:
    case = db.get(CaseModel, case_id)
    if case is None:
        raise ValueError(f"Case {case_id} was not found")
    documents = list(
        db.scalars(
            select(DocumentModel)
            .where(DocumentModel.case_id == case_id)
            .order_by(DocumentModel.created_at)
        )
    )
    document_views: list[DocumentView] = []
    all_fields = list(
        db.scalars(select(ExtractedFieldModel).where(ExtractedFieldModel.case_id == case_id))
    )
    for document in documents:
        fields = [field for field in all_fields if field.document_id == document.id]
        document_views.append(
            DocumentView(
                id=document.id,
                filename=document.filename,
                mime_type=document.mime_type,
                size_bytes=document.size_bytes,
                page_count=document.page_count,
                document_type=document.document_type,
                classification_confidence=document.classification_confidence,
                status=document.status,
                sha256=document.sha256,
                fields=[
                    FieldView(
                        id=field.id,
                        field_name=field.field_name,
                        value=field.value_json,
                        confidence=field.confidence,
                        extraction_confidence=field.extraction_confidence,
                        ocr_confidence=field.ocr_confidence,
                        validation_status=field.validation_status,
                        status=field.status,
                        method=field.method,
                        warnings=field.warnings_json or [],
                        evidence=_evidence_views(db, field.id),
                    )
                    for field in fields
                ],
            )
        )
    validations = list(
        db.scalars(select(ValidationResultModel).where(ValidationResultModel.case_id == case_id))
    )
    reconciliations = list(
        db.scalars(select(ReconciliationModel).where(ReconciliationModel.case_id == case_id))
    )
    reviews = list(
        db.scalars(
            select(ReviewItemModel)
            .where(ReviewItemModel.case_id == case_id)
            .order_by(ReviewItemModel.created_at.desc())
        )
    )
    return CaseView(
        id=case.id,
        name=case.name,
        property_address=case.property_address,
        status=case.status,
        documents=document_views,
        validations=[
            ValidationView(
                id=row.id,
                rule_id=row.rule_id,
                status=row.status,
                message=row.message,
                expected=row.expected_json,
                actual=row.actual_json,
            )
            for row in validations
        ],
        reconciliations=[
            ReconciliationView(
                id=row.id,
                metric=row.metric,
                status=row.status,
                left_document_id=row.left_document_id,
                right_document_id=row.right_document_id,
                left_value=row.left_value_json,
                right_value=row.right_value_json,
                difference=row.difference,
                message=row.message,
            )
            for row in reconciliations
        ],
        reviews=[
            ReviewView(
                id=row.id,
                document_id=row.document_id,
                field_id=row.field_id,
                status=row.status,
                reason=row.reason,
                model_value=row.model_value_json,
                human_value=row.human_value_json,
                reviewer=row.reviewer,
            )
            for row in reviews
        ],
        verified_field_count=sum(
            1 for field in all_fields if field.status == "accepted" and field.confidence >= 0.75
        ),
        reviewed_field_count=sum(1 for row in reviews if row.status == "resolved"),
        # Reconciliation conflicts are represented by a linked review item, so do not
        # double-count the same exception in the case header.
        exception_count=sum(1 for row in reviews if row.status == "open"),
        overall_confidence=round(
            sum(field.confidence for field in all_fields) / len(all_fields) if all_fields else 0.0,
            4,
        ),
    )
