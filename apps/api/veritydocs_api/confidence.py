from __future__ import annotations

from collections.abc import Iterable


def field_confidence(
    extraction_confidence: float,
    ocr_confidence: float,
    validation_statuses: Iterable[str],
    corroborated: bool = False,
) -> float:
    """Compute an explainable composite score instead of trusting model self-reporting."""
    statuses = list(validation_statuses)
    schema_score = 1.0 if not statuses or all(status != "FAIL" for status in statuses) else 0.45
    validation_score = 1.0 if not statuses or any(status == "PASS" for status in statuses) else 0.7
    if any(status == "FAIL" for status in statuses):
        validation_score = 0.25
    corroboration_score = 1.0 if corroborated else 0.55
    score = (
        0.45 * extraction_confidence
        + 0.20 * max(0.0, min(1.0, ocr_confidence))
        + 0.15 * schema_score
        + 0.10 * validation_score
        + 0.10 * corroboration_score
    )
    return round(max(0.0, min(1.0, score)), 4)


def needs_review(
    confidence: float, statuses: Iterable[str], value_is_missing: bool = False
) -> bool:
    status_list = list(statuses)
    return (
        value_is_missing
        or confidence < 0.75
        or any(status in {"FAIL", "CONFLICT", "UNABLE_TO_VERIFY"} for status in status_list)
    )
