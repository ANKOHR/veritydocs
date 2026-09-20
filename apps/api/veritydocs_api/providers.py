from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from pydantic import BaseModel

from .config import Settings
from .pipeline.types import NormalizedDocument
from .schemas import (
    ClassificationResult,
    ContractExtraction,
    InvoiceExtraction,
    LoanSummaryExtraction,
    OperatingStatementExtraction,
    PaymentApplicationExtraction,
    PropertyTaxExtraction,
    RentRollExtraction,
)


class ProviderNotConfigured(RuntimeError):
    pass


EXTRACTION_SCHEMAS: dict[str, type[BaseModel]] = {
    "rent_roll": RentRollExtraction,
    "operating_statement": OperatingStatementExtraction,
    "loan_summary": LoanSummaryExtraction,
    "tax_record": PropertyTaxExtraction,
    "invoice": InvoiceExtraction,
    "contract": ContractExtraction,
    "payment_application": PaymentApplicationExtraction,
}


@dataclass
class ProviderResult:
    model: BaseModel
    provider: str
    model_name: str
    extraction_confidence: float


class ExtractionProvider(Protocol):
    name: str
    model_name: str

    def classify(self, document: NormalizedDocument) -> ClassificationResult: ...

    def extract(self, document_type: str, document: NormalizedDocument) -> ProviderResult: ...


def _money(text: str, label: str) -> Decimal | None:
    match = re.search(
        rf"{re.escape(label)}[^£$\d-]*[£$]?\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE
    )
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(",", ""))
    except InvalidOperation:
        return None


def _percent(text: str, label: str) -> Decimal | None:
    match = re.search(rf"{re.escape(label)}[^\d]*([\d.]+)\s*%", text, re.IGNORECASE)
    return Decimal(match.group(1)) if match else None


def _int(text: str, label: str) -> int | None:
    match = re.search(rf"{re.escape(label)}[^\d]*(\d+)", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            if fmt == "%Y-%m-%d":
                return date.fromisoformat(value)
            separator = "/" if "/" in value else "-"
            day, month, year = (int(part) for part in value.split(separator))
            return date(year, month, day)
        except ValueError:
            continue
    return None


class DemoExtractionProvider:
    """Credential-free provider for reproducible fixtures and local product demonstrations."""

    name = "demo"
    model_name = "deterministic-document-0"

    def classify(self, document: NormalizedDocument) -> ClassificationResult:
        haystack = f"{document.filename} {document.text}".lower()
        candidates = [
            ("rent_roll", ("rent" in haystack and "unit" in haystack) or "rent_roll" in haystack),
            ("operating_statement", "operating" in haystack or "noi" in haystack),
            ("loan_summary", "loan" in haystack or "interest rate" in haystack),
            ("tax_record", "property tax" in haystack or "tax notice" in haystack),
            ("invoice", "invoice" in haystack or "vat" in haystack),
            (
                "payment_application",
                "payment application" in haystack or "application for payment" in haystack,
            ),
            ("contract", "contract" in haystack or "obligation" in haystack),
        ]
        matches = [(kind, 0.97 if match else 0.01) for kind, match in candidates]
        matches.sort(key=lambda item: item[1], reverse=True)
        best, confidence = matches[0]
        if confidence < 0.5:
            best, confidence = "unknown", 0.2
        return ClassificationResult(
            document_type=best,
            confidence=confidence,
            alternatives=[{"type": kind, "confidence": score} for kind, score in matches[1:3]],
        )

    def extract(self, document_type: str, document: NormalizedDocument) -> ProviderResult:
        text = document.text
        if document_type == "rent_roll":
            units = []
            table = (
                document.pages[0].tables[0] if document.pages and document.pages[0].tables else None
            )
            if table:
                headers = [header.lower().replace("_", " ") for header in table.headers]
                for row in table.rows:
                    values = dict(zip(headers, row, strict=False))
                    unit_id = str(values.get("unit") or values.get("unit id") or "unknown")
                    rent_value = values.get("monthly rent") or values.get("rent")
                    rent = Decimal(str(rent_value).replace(",", "")) if rent_value else None
                    units.append(
                        {
                            "unit_id": unit_id,
                            "status": values.get("status"),
                            "monthly_rent": rent,
                            "lease_end": _date(values.get("lease end")),
                        }
                    )
            model = RentRollExtraction(
                property_address="32 New Street, London"
                if "32 new street" in text.lower()
                else None,
                units=units,
                total_units=_int(text, "Total units") or (len(units) or None),
                occupied_units=_int(text, "Occupied units"),
                reported_monthly_rent=_money(text, "Reported monthly rent"),
            )
        elif document_type == "operating_statement":
            model = OperatingStatementExtraction(
                property_address="32 New Street, London"
                if "32 new street" in text.lower()
                else None,
                reporting_period=(
                    re.search(r"Reporting period:\s*([^\n]+)", text, re.IGNORECASE) or [None, None]
                )[1],
                rental_income=_money(text, "Rental income"),
                annual_revenue=_money(text, "Annual revenue"),
                operating_expenses=_money(text, "Operating expenses"),
                annual_noi=_money(text, "Annual NOI"),
            )
        elif document_type == "loan_summary":
            model = LoanSummaryExtraction(
                property_address="32 New Street, London"
                if "32 new street" in text.lower()
                else None,
                loan_balance=_money(text, "Loan balance"),
                interest_rate=_percent(text, "Interest rate"),
            )
        elif document_type == "tax_record":
            model = PropertyTaxExtraction(
                property_address="32 New Street, London"
                if "32 new street" in text.lower()
                else None,
                accounting_period=(
                    re.search(r"Accounting period:\s*([^\n]+)", text, re.IGNORECASE) or [None, None]
                )[1],
                annual_property_tax=_money(text, "Annual property tax"),
            )
        elif document_type == "invoice":
            model = InvoiceExtraction(
                supplier_name=(
                    re.search(r"Supplier:\s*([^\n]+)", text, re.IGNORECASE) or [None, None]
                )[1],
                invoice_number=(
                    re.search(r"Invoice number:\s*([^\n]+)", text, re.IGNORECASE) or [None, None]
                )[1],
                currency="GBP" if "£" in text or "gbp" in text.lower() else None,
                net=_money(text, "Net"),
                tax=_money(text, "VAT") or _money(text, "Tax"),
                gross=_money(text, "Gross") or _money(text, "Total"),
            )
        elif document_type == "contract":
            model = ContractExtraction(
                project_name=(
                    re.search(r"Project:\s*([^\n]+)", text, re.IGNORECASE) or [None, None]
                )[1],
                contract_reference=(
                    re.search(r"(?:Contract reference|Reference):\s*([^\n]+)", text, re.IGNORECASE)
                    or [None, None]
                )[1],
                contractor=(
                    re.search(r"Contractor:\s*([^\n]+)", text, re.IGNORECASE) or [None, None]
                )[1],
                total_contract_value=_money(text, "Contract value") or _money(text, "Total value"),
                currency="GBP" if "£" in text or "gbp" in text.lower() else None,
                commencement_date=_date(
                    (
                        re.search(r"Commencement date:\s*([^\n]+)", text, re.IGNORECASE)
                        or [None, None]
                    )[1]
                ),
                completion_date=_date(
                    (
                        re.search(r"Completion date:\s*([^\n]+)", text, re.IGNORECASE)
                        or [None, None]
                    )[1]
                ),
                payment_terms_days=_int(text, "Payment terms"),
            )
        elif document_type == "payment_application":
            model = PaymentApplicationExtraction(
                project_name=(
                    re.search(r"Project:\s*([^\n]+)", text, re.IGNORECASE) or [None, None]
                )[1],
                contract_reference=(
                    re.search(r"Contract reference:\s*([^\n]+)", text, re.IGNORECASE)
                    or [None, None]
                )[1],
                application_number=(
                    re.search(r"Application number:\s*([^\n]+)", text, re.IGNORECASE)
                    or [None, None]
                )[1],
                applicant=(
                    re.search(r"Applicant:\s*([^\n]+)", text, re.IGNORECASE) or [None, None]
                )[1],
                claimed_amount=_money(text, "Claimed amount"),
                application_period=(
                    re.search(r"Application period:\s*([^\n]+)", text, re.IGNORECASE)
                    or [None, None]
                )[1],
                payment_due_date=_date(
                    (
                        re.search(r"Payment due date:\s*([^\n]+)", text, re.IGNORECASE)
                        or [None, None]
                    )[1]
                ),
            )
        else:
            schema = EXTRACTION_SCHEMAS.get(document_type)
            model = (
                schema()
                if schema
                else ClassificationResult(document_type="unknown", confidence=0.2)
            )
        confidence = 0.96 if document.average_ocr_confidence >= 0.9 else 0.72
        return ProviderResult(
            model=model,
            provider=self.name,
            model_name=self.model_name,
            extraction_confidence=confidence,
        )


class OpenAIMultimodalProvider:
    """Structured multimodal adapter; it is never called without an explicit API key."""

    name = "openai"

    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise ProviderNotConfigured(
                "OPENAI_API_KEY is required for the OpenAI extraction provider"
            )
        from openai import OpenAI

        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model_name = settings.openai_model

    def _structured(
        self, schema: type[BaseModel], prompt: str, image_keys: list[str] | None = None
    ) -> BaseModel:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        for key in image_keys or []:
            content.append({"type": "input_image", "image_url": key})
        response = self.client.responses.create(
            model=self.model_name,
            input=[{"role": "user", "content": content}],
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema.__name__,
                    "schema": schema.model_json_schema(),
                    "strict": True,
                }
            },
        )
        return schema.model_validate(json.loads(response.output_text))

    def classify(self, document: NormalizedDocument) -> ClassificationResult:
        prompt = (
            "Classify this document into rent_roll, operating_statement, loan_summary, tax_record, invoice, contract or unknown. Return only the requested schema.\n\n"
            + document.text[:80_000]
        )
        return self._structured(ClassificationResult, prompt)  # type: ignore[return-value]

    def extract(self, document_type: str, document: NormalizedDocument) -> ProviderResult:
        schema = EXTRACTION_SCHEMAS.get(document_type)
        if schema is None:
            raise ValueError(f"No extraction schema for {document_type}")
        prompt = f"Extract a {document_type} from the normalized document. Preserve uncertainty as null and never invent unsupported values.\n\n{document.text[:100_000]}"
        model = self._structured(schema, prompt)
        return ProviderResult(
            model=model, provider=self.name, model_name=self.model_name, extraction_confidence=0.0
        )
