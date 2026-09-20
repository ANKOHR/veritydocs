from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class ValidationOutcome:
    rule_id: str
    status: str
    message: str
    expected: Any = None
    actual: Any = None


def _number(value: Decimal | float | None) -> float | None:
    return None if value is None else float(value)


def validate_document(document_type: str, model: BaseModel) -> list[ValidationOutcome]:
    """Run deterministic checks over a typed extraction; no model call is made here."""
    outcomes: list[ValidationOutcome] = []
    if document_type == "invoice":
        net = getattr(model, "net", None)
        tax = getattr(model, "tax", None)
        gross = getattr(model, "gross", None)
        if net is None or tax is None or gross is None:
            outcomes.append(
                ValidationOutcome(
                    "FIN-001",
                    "UNABLE_TO_VERIFY",
                    "Invoice arithmetic is missing net, tax, or gross.",
                )
            )
        else:
            expected = net + tax
            status = "PASS" if abs(expected - gross) <= Decimal("0.01") else "FAIL"
            outcomes.append(
                ValidationOutcome(
                    "FIN-001",
                    status,
                    f"Gross {'equals' if status == 'PASS' else 'does not equal'} net plus tax.",
                    _number(expected),
                    _number(gross),
                )
            )

    if document_type == "rent_roll":
        units = getattr(model, "units", [])
        total_units = getattr(model, "total_units", None)
        if total_units is None:
            outcomes.append(
                ValidationOutcome("RR-004", "UNABLE_TO_VERIFY", "Total unit count is missing.")
            )
        else:
            status = "PASS" if total_units == len(units) else "FAIL"
            outcomes.append(
                ValidationOutcome(
                    "RR-004",
                    status,
                    f"Reported unit count {total_units} vs extracted rows {len(units)}.",
                    total_units,
                    len(units),
                )
            )
        reported = getattr(model, "reported_monthly_rent", None)
        rents = [unit.monthly_rent for unit in units if unit.monthly_rent is not None]
        if reported is None or len(rents) != len(units):
            outcomes.append(
                ValidationOutcome(
                    "RR-007",
                    "UNABLE_TO_VERIFY",
                    "Reported rent or one or more unit rents is missing.",
                )
            )
        else:
            computed = sum(rents, Decimal(0))
            status = "PASS" if abs(computed - reported) <= Decimal("0.01") else "FAIL"
            outcomes.append(
                ValidationOutcome(
                    "RR-007",
                    status,
                    f"Reported monthly rent {reported} vs computed total {computed}.",
                    _number(reported),
                    _number(computed),
                )
            )

    if document_type == "operating_statement":
        revenue = getattr(model, "annual_revenue", None)
        expenses = getattr(model, "operating_expenses", None)
        noi = getattr(model, "annual_noi", None)
        if revenue is None or expenses is None or noi is None:
            outcomes.append(
                ValidationOutcome(
                    "OS-003", "UNABLE_TO_VERIFY", "Annual revenue, expenses, or NOI is missing."
                )
            )
        else:
            computed = revenue - expenses
            status = "PASS" if abs(computed - noi) <= Decimal("0.01") else "FAIL"
            outcomes.append(
                ValidationOutcome(
                    "OS-003",
                    status,
                    f"NOI {noi} vs revenue less expenses {computed}.",
                    _number(noi),
                    _number(computed),
                )
            )

    if document_type == "tax_record":
        tax = getattr(model, "annual_property_tax", None)
        outcomes.append(
            ValidationOutcome(
                "TAX-001",
                "PASS" if tax is not None else "UNABLE_TO_VERIFY",
                "Annual property tax is present."
                if tax is not None
                else "Annual property tax is missing.",
                _number(tax),
                _number(tax),
            )
        )

    if document_type == "loan_summary":
        balance = getattr(model, "loan_balance", None)
        rate = getattr(model, "interest_rate", None)
        status = "PASS" if balance is not None and rate is not None else "UNABLE_TO_VERIFY"
        outcomes.append(
            ValidationOutcome(
                "LOAN-001",
                status,
                "Loan balance and interest rate are present."
                if status == "PASS"
                else "Loan balance or interest rate is missing.",
                {"loan_balance": _number(balance), "interest_rate": _number(rate)},
                {"loan_balance": _number(balance), "interest_rate": _number(rate)},
            )
        )

    if document_type == "contract":
        reference = getattr(model, "contract_reference", None)
        value = getattr(model, "total_contract_value", None)
        status = "PASS" if reference and value is not None else "UNABLE_TO_VERIFY"
        outcomes.append(
            ValidationOutcome(
                "CON-001",
                status,
                "Contract reference and total value are present."
                if status == "PASS"
                else "Contract reference or total value is missing.",
                {"contract_reference": reference, "total_contract_value": _number(value)},
                {"contract_reference": reference, "total_contract_value": _number(value)},
            )
        )

    if document_type == "payment_application":
        reference = getattr(model, "contract_reference", None)
        amount = getattr(model, "claimed_amount", None)
        status = "PASS" if reference and amount is not None else "UNABLE_TO_VERIFY"
        outcomes.append(
            ValidationOutcome(
                "PAY-001",
                status,
                "Payment application reference and claimed amount are present."
                if status == "PASS"
                else "Payment application reference or claimed amount is missing.",
                {"contract_reference": reference, "claimed_amount": _number(amount)},
                {"contract_reference": reference, "claimed_amount": _number(amount)},
            )
        )

    if not outcomes:
        outcomes.append(
            ValidationOutcome("DOC-000", "UNABLE_TO_VERIFY", "No validation rules apply.")
        )
    return outcomes
