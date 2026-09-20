from decimal import Decimal

from veritydocs_api.confidence import field_confidence, needs_review
from veritydocs_api.schemas import InvoiceExtraction, OperatingStatementExtraction
from veritydocs_api.validation import validate_document


def test_invoice_arithmetic_fails_closed_on_wrong_total():
    outcomes = validate_document(
        "invoice",
        InvoiceExtraction(net=Decimal(10000), tax=Decimal(2000), gross=Decimal(12500)),
    )
    assert outcomes[0].rule_id == "FIN-001"
    assert outcomes[0].status == "FAIL"


def test_operating_statement_noi_rule_passes():
    outcomes = validate_document(
        "operating_statement",
        OperatingStatementExtraction(
            annual_revenue=Decimal(1049040),
            operating_expenses=Decimal(336200),
            annual_noi=Decimal(712840),
        ),
    )
    assert {outcome.status for outcome in outcomes} == {"PASS"}


def test_confidence_routes_missing_or_conflicted_values_to_review():
    score = field_confidence(0.96, 1.0, ["PASS"])
    assert score > 0.8
    assert needs_review(0.9, ["CONFLICT"])
    assert needs_review(0.9, [], value_is_missing=True)


def test_openai_adapter_requires_explicit_key():
    from veritydocs_api.config import Settings
    from veritydocs_api.providers import OpenAIMultimodalProvider, ProviderNotConfigured

    try:
        OpenAIMultimodalProvider(Settings(openai_api_key=None))
    except ProviderNotConfigured:
        pass
    else:
        raise AssertionError("OpenAI adapter must fail closed without a key")
