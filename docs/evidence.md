# VerityDocs evidence record

This file deliberately separates what is verified in this workspace from what is only designed.

## Verified locally

Date of this record: 2026-09-20

- Python environment: Python 3.13.5.
- `ruff check .`: passed.
- `pytest -q`: 48 passed; two dependency deprecation warnings.
- `pnpm typecheck`: passed.
- `pnpm build`: passed with Next.js 16.3.5.
- Alembic initial migration generated and applied locally; revision `73c601621fe6` is the current
  head in the local SQLite check.
- The seeded Acme case processes four generated source documents: one deliberately offset XLSX
  rent roll and three native-text PDFs.
- The seeded case produced 19 persisted top-level fields, five passing deterministic validation
  rules, two reconciled comparisons plus one deliberate accounting-period conflict, and two open
  review items (Unit 3B missing a lease-end date; tax period conflicts with the operating period).
- A loan balance is shown as extracted but `UNABLE_TO_VERIFY` for cross-document corroboration when
  a second balance source is absent.
- Exact duplicate uploads return the original document ID and do not start another processing run.
- A tenant header for a different tenant cannot read the case.
- Review resolution stores the reviewer, human decision and an audit event.
- The contract/payment fixture path extracts both document types and surfaces a deliberate
  `payment_against_contract_value` conflict when the claim exceeds the agreement value.
- The synthetic scanned-invoice fixtures are image-only PDFs; the public case workspace uploads
  them through `run_pipeline=false`, and the S3-compatible adapter is ready for a shared API/worker
  object store.
- The 100-case evaluation runner reports 100% on its synthetic template corpus for classification,
  schema validity, exact values, evidence-page matching and deliberately wrong invoice-total
  detection. This is a fixture result only, not a real-world accuracy claim.

## Not claimed

- No production deployment has been performed from this repository.
- No real customer document has been processed.
- The OpenAI provider adapter is present but was not called because no API key was supplied or
  created.
- Tesseract was not available on the Windows host during the smoke test. The adapter is implemented,
  the worker image installs Tesseract and logs its version at startup, but local OCR quality is not
  claimed until the deployed worker exercises it.
- PostgreSQL/Redis/Dramatiq wiring is represented and covered by Docker configuration, but a live
  Docker daemon run is not claimed by this record.
- No compliance certification or security audit is claimed.

## Reproduce the checks

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest -q
pnpm typecheck
pnpm build
.venv\Scripts\python.exe packages\evals\run_evals.py --write docs\eval-results.json
.venv\Scripts\alembic.exe upgrade head
```
