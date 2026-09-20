from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETE = "complete"
    REVIEW = "requires_review"
    FAILED = "failed"


class ReviewStatus(StrEnum):
    VERIFIED = "verified"
    PROBABLE = "probable"
    CONFLICT = "conflict"
    MISSING = "missing"
    UNABLE_TO_VERIFY = "unable_to_verify"
    REQUIRES_REVIEW = "requires_review"


class EvidenceRef(BaseModel):
    document_id: str
    page: int = Field(ge=1)
    text: str
    bbox: list[float] | None = None
    section: str | None = None
    artifact_key: str | None = None


class UnitExtraction(BaseModel):
    unit_id: str
    status: str | None = None
    monthly_rent: Decimal | None = None
    lease_end: date | None = None


class RentRollExtraction(BaseModel):
    property_address: str | None = None
    report_date: date | None = None
    units: list[UnitExtraction] = Field(default_factory=list)
    total_units: int | None = None
    occupied_units: int | None = None
    reported_monthly_rent: Decimal | None = None


class OperatingStatementExtraction(BaseModel):
    property_address: str | None = None
    reporting_period: str | None = None
    rental_income: Decimal | None = None
    annual_revenue: Decimal | None = None
    operating_expenses: Decimal | None = None
    annual_noi: Decimal | None = None


class LoanSummaryExtraction(BaseModel):
    property_address: str | None = None
    loan_balance: Decimal | None = None
    interest_rate: Decimal | None = None
    maturity_date: date | None = None


class PropertyTaxExtraction(BaseModel):
    property_address: str | None = None
    accounting_period: str | None = None
    annual_property_tax: Decimal | None = None


class InvoiceExtraction(BaseModel):
    supplier_name: str | None = None
    invoice_number: str | None = None
    issue_date: date | None = None
    currency: str | None = None
    net: Decimal | None = None
    tax: Decimal | None = None
    gross: Decimal | None = None
    line_items: list[dict[str, Any]] = Field(default_factory=list)


class ContractExtraction(BaseModel):
    project_name: str | None = None
    contract_reference: str | None = None
    contractor: str | None = None
    total_contract_value: Decimal | None = None
    currency: str | None = None
    commencement_date: date | None = None
    completion_date: date | None = None
    payment_terms_days: int | None = None
    obligations: list[dict[str, Any]] = Field(default_factory=list)


class PaymentApplicationExtraction(BaseModel):
    project_name: str | None = None
    contract_reference: str | None = None
    application_number: str | None = None
    applicant: str | None = None
    claimed_amount: Decimal | None = None
    application_period: str | None = None
    payment_due_date: date | None = None


class ClassificationResult(BaseModel):
    document_type: str
    confidence: float = Field(ge=0, le=1)
    alternatives: list[dict[str, float | str]] = Field(default_factory=list)


class FieldView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    field_name: str
    value: Any
    confidence: float
    extraction_confidence: float
    ocr_confidence: float
    validation_status: str
    status: str
    method: str
    warnings: list[str]
    evidence: list[EvidenceRef]


class DocumentView(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    page_count: int
    document_type: str
    classification_confidence: float
    status: str
    sha256: str
    fields: list[FieldView]


class ValidationView(BaseModel):
    id: str
    rule_id: str
    status: str
    message: str
    expected: Any = None
    actual: Any = None


class ReconciliationView(BaseModel):
    id: str
    metric: str
    status: str
    left_document_id: str | None
    right_document_id: str | None
    left_value: Any = None
    right_value: Any = None
    difference: float | None
    message: str


class ReviewView(BaseModel):
    id: str
    document_id: str
    field_id: str | None
    status: str
    reason: str
    model_value: Any = None
    human_value: Any = None
    reviewer: str | None


class CaseView(BaseModel):
    id: str
    name: str
    property_address: str | None
    status: str
    documents: list[DocumentView]
    validations: list[ValidationView]
    reconciliations: list[ReconciliationView]
    reviews: list[ReviewView]
    verified_field_count: int
    reviewed_field_count: int
    exception_count: int
    overall_confidence: float


class ReviewDecision(BaseModel):
    decision: str
    value: Any = None
    reviewer: str = "operator"
    reason: str | None = None
