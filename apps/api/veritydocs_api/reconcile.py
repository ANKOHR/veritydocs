from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class DocumentFacts:
    document_id: str
    document_type: str
    model: Any


@dataclass(frozen=True)
class ReconciliationOutcome:
    metric: str
    status: str
    left_document_id: str | None
    right_document_id: str | None
    left_value: Any
    right_value: Any
    difference: float | None
    message: str


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.lower().replace(",", "").split())


def reconcile_case(documents: list[DocumentFacts]) -> list[ReconciliationOutcome]:
    outcomes: list[ReconciliationOutcome] = []
    by_type = {document.document_type: document for document in documents}

    address_sources = [
        (document, getattr(document.model, "property_address", None))
        for document in documents
        if getattr(document.model, "property_address", None)
    ]
    if len(address_sources) >= 2:
        first_document, first_value = address_sources[0]
        conflicts = [item for item in address_sources[1:] if _norm(item[1]) != _norm(first_value)]
        outcomes.append(
            ReconciliationOutcome(
                "property_address",
                "CONFLICT" if conflicts else "RECONCILED",
                first_document.document_id,
                conflicts[0][0].document_id if conflicts else address_sources[1][0].document_id,
                first_value,
                conflicts[0][1] if conflicts else address_sources[1][1],
                None,
                "Property address agrees across documents."
                if not conflicts
                else "Property address conflicts across documents.",
            )
        )

    rent_roll = by_type.get("rent_roll")
    operating = by_type.get("operating_statement")
    rent_value = getattr(rent_roll.model, "reported_monthly_rent", None) if rent_roll else None
    operating_value = getattr(operating.model, "rental_income", None) if operating else None
    if rent_roll and operating and rent_value is not None and operating_value is not None:
        difference = float(rent_value - operating_value)
        status = "RECONCILED" if abs(difference) <= 0.01 else "CONFLICT"
        outcomes.append(
            ReconciliationOutcome(
                "monthly_rent",
                status,
                rent_roll.document_id,
                operating.document_id,
                float(rent_value),
                float(operating_value),
                difference,
                "Rent roll and operating statement monthly rental income agree."
                if status == "RECONCILED"
                else "Monthly rental income differs between documents.",
            )
        )
    else:
        outcomes.append(
            ReconciliationOutcome(
                "monthly_rent",
                "UNABLE_TO_VERIFY",
                rent_roll.document_id if rent_roll else None,
                operating.document_id if operating else None,
                float(rent_value) if isinstance(rent_value, Decimal) else rent_value,
                float(operating_value) if isinstance(operating_value, Decimal) else operating_value,
                None,
                "Monthly rent cannot be compared until both source values are present.",
            )
        )

    tax = by_type.get("tax_record")
    if tax and operating:
        tax_period = getattr(tax.model, "accounting_period", None)
        operating_period = getattr(operating.model, "reporting_period", None)
        if tax_period and operating_period:
            status = "RECONCILED" if _norm(tax_period) == _norm(operating_period) else "CONFLICT"
            outcomes.append(
                ReconciliationOutcome(
                    "accounting_period",
                    status,
                    tax.document_id,
                    operating.document_id,
                    tax_period,
                    operating_period,
                    None,
                    "Tax and operating statement periods agree."
                    if status == "RECONCILED"
                    else "Tax document covers a different accounting period.",
                )
            )

    loan = by_type.get("loan_summary")
    if loan:
        balance = getattr(loan.model, "loan_balance", None)
        outcomes.append(
            ReconciliationOutcome(
                "loan_balance_corroboration",
                "UNABLE_TO_VERIFY",
                loan.document_id,
                None,
                float(balance) if isinstance(balance, Decimal) else balance,
                None,
                None,
                "Loan balance is extracted, but no second balance source is available for corroboration.",
            )
        )

    contract = by_type.get("contract")
    payment = by_type.get("payment_application")
    if contract and payment:
        contract_reference = getattr(contract.model, "contract_reference", None)
        payment_reference = getattr(payment.model, "contract_reference", None)
        if contract_reference and payment_reference:
            reference_status = (
                "RECONCILED"
                if _norm(contract_reference) == _norm(payment_reference)
                else "CONFLICT"
            )
            outcomes.append(
                ReconciliationOutcome(
                    "contract_reference",
                    reference_status,
                    contract.document_id,
                    payment.document_id,
                    contract_reference,
                    payment_reference,
                    None,
                    "Contract reference agrees across the agreement and payment application."
                    if reference_status == "RECONCILED"
                    else "Payment application references a different contract.",
                )
            )
        else:
            outcomes.append(
                ReconciliationOutcome(
                    "contract_reference",
                    "UNABLE_TO_VERIFY",
                    contract.document_id,
                    payment.document_id,
                    contract_reference,
                    payment_reference,
                    None,
                    "Contract reference cannot be compared until both documents provide one.",
                )
            )

        contract_value = getattr(contract.model, "total_contract_value", None)
        claimed_amount = getattr(payment.model, "claimed_amount", None)
        if contract_value is not None and claimed_amount is not None:
            difference = float(claimed_amount - contract_value)
            amount_status = "RECONCILED" if claimed_amount <= contract_value else "CONFLICT"
            outcomes.append(
                ReconciliationOutcome(
                    "payment_against_contract_value",
                    amount_status,
                    contract.document_id,
                    payment.document_id,
                    float(contract_value),
                    float(claimed_amount),
                    difference,
                    "Claimed amount is within the contract value."
                    if amount_status == "RECONCILED"
                    else "Claimed amount exceeds the contract value.",
                )
            )
        else:
            outcomes.append(
                ReconciliationOutcome(
                    "payment_against_contract_value",
                    "UNABLE_TO_VERIFY",
                    contract.document_id,
                    payment.document_id,
                    float(contract_value)
                    if isinstance(contract_value, Decimal)
                    else contract_value,
                    float(claimed_amount)
                    if isinstance(claimed_amount, Decimal)
                    else claimed_amount,
                    None,
                    "Payment cannot be compared until both contract and claim values are present.",
                )
            )
    return outcomes
