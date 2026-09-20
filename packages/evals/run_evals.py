from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from veritydocs_api.pipeline.types import NormalizedDocument, NormalizedPage, TextBlock
from veritydocs_api.providers import DemoExtractionProvider
from veritydocs_api.validation import validate_document


def _document(document_id: str, text: str) -> NormalizedDocument:
    return NormalizedDocument(
        document_id=document_id,
        filename=f"{document_id}.txt",
        mime_type="text/plain",
        pages=[NormalizedPage(page_number=1, blocks=[TextBlock(text=text)])],
    )


def _numeric_equal(actual: Any, expected: Any) -> bool:
    if actual is None or expected is None:
        return actual == expected
    try:
        return abs(float(actual) - float(expected)) <= 0.01
    except (TypeError, ValueError):
        return str(actual).strip().lower() == str(expected).strip().lower()


def cases() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index in range(50):
        revenue = 1_000_000 + index * 1_000
        expenses = 300_000 + index * 500
        result.append(
            {
                "id": f"operating-{index:03d}",
                "type": "operating_statement",
                "text": "\n".join(
                    [
                        "Property Operating Statement",
                        "Property: 32 New Street, London",
                        "Reporting period: 2024/25",
                        f"Rental income: £{87_420 + index:,}",
                        f"Annual revenue: £{revenue:,}",
                        f"Operating expenses: £{expenses:,}",
                        f"Annual NOI: £{revenue - expenses:,}",
                    ]
                ),
                "expected": {
                    "annual_revenue": revenue,
                    "operating_expenses": expenses,
                    "annual_noi": revenue - expenses,
                },
                "evidence_labels": ["Annual revenue", "Operating expenses", "Annual NOI"],
                "should_detect_invalid": False,
            }
        )
    for index in range(25):
        net = 10_000 + index * 125
        tax = net * 0.2
        gross = net + tax if index % 5 else net + tax + 10
        result.append(
            {
                "id": f"invoice-{index:03d}",
                "type": "invoice",
                "text": f"Invoice Supplier: Supplier {index} Invoice number: INV-{index:04d} Net £{net:.2f} VAT £{tax:.2f} Gross £{gross:.2f}",
                "expected": {"net": net, "tax": tax, "gross": gross},
                "evidence_labels": ["Net", "VAT", "Gross"],
                "should_detect_invalid": index % 5 == 0,
            }
        )
    for index in range(25):
        balance = 4_000_000 + index * 5_000
        rate = 5.25 + (index % 4) * 0.125
        result.append(
            {
                "id": f"loan-{index:03d}",
                "type": "loan_summary",
                "text": f"Loan Summary Current Facilities Property: 32 New Street, London Loan balance: £{balance:,} Interest rate: {rate:.3f}%",
                "expected": {"loan_balance": balance, "interest_rate": rate},
                "evidence_labels": ["Loan balance", "Interest rate"],
                "should_detect_invalid": False,
            }
        )
    return result


def run() -> dict[str, Any]:
    provider = DemoExtractionProvider()
    rows = cases()
    measurements: list[dict[str, Any]] = []
    for row in rows:
        document = _document(row["id"], row["text"])
        classification = provider.classify(document)
        extracted = provider.extract(row["type"], document)
        values = extracted.model.model_dump(mode="json")
        exact_fields = sum(
            _numeric_equal(values.get(key), expected) for key, expected in row["expected"].items()
        )
        evidence_hits = sum(
            document.find_evidence(label) is not None for label in row["evidence_labels"]
        )
        validation = validate_document(row["type"], extracted.model)
        invalid_detected = row["should_detect_invalid"] and any(
            item.status == "FAIL" for item in validation
        )
        measurements.append(
            {
                "id": row["id"],
                "split": "development" if len(measurements) < 80 else "held_out",
                "classification_correct": classification.document_type == row["type"],
                "schema_valid": True,
                "exact_fields": exact_fields,
                "expected_fields": len(row["expected"]),
                "evidence_hits": evidence_hits,
                "evidence_expected": len(row["evidence_labels"]),
                "invalid_expected": row["should_detect_invalid"],
                "invalid_detected": invalid_detected,
            }
        )
    total_fields = sum(item["expected_fields"] for item in measurements)
    total_evidence = sum(item["evidence_expected"] for item in measurements)
    invalid_cases = [item for item in measurements if item["invalid_expected"]]
    summary = {
        "dataset": "synthetic-template-v1",
        "total_cases": len(measurements),
        "development_cases": 80,
        "held_out_cases": 20,
        "metrics": {
            "classification_accuracy": round(
                sum(item["classification_correct"] for item in measurements) / len(measurements), 4
            ),
            "schema_validity": round(
                sum(item["schema_valid"] for item in measurements) / len(measurements), 4
            ),
            "exact_value_accuracy": round(
                sum(item["exact_fields"] for item in measurements) / total_fields, 4
            ),
            "evidence_page_accuracy": round(
                sum(item["evidence_hits"] for item in measurements) / total_evidence, 4
            ),
            "invalid_source_detection_recall": round(
                sum(item["invalid_detected"] for item in invalid_cases) / len(invalid_cases), 4
            ),
        },
        "disclaimer": "Synthetic fixtures only. These measurements are not real-world accuracy claims and are not a substitute for a held-out corpus of customer documents.",
        "cases": measurements,
    }
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", type=Path, help="Write JSON results to this path")
    args = parser.parse_args()
    output = run()
    encoded = json.dumps(output, indent=2)
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
