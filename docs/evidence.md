# VerityDocs evidence record

This file deliberately separates what is verified in this workspace from what is only designed.

## Verified locally

Date of this record: 2026-09-20

- Python environment: Python 3.13.5.
- `ruff check .`: passed.
- `pytest -q`: 49 passed; two dependency deprecation warnings.
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

## Verified externally

Date of this record: 2026-09-20

- Public repository: [`ANKOHR/veritydocs`](https://github.com/ANKOHR/veritydocs), with the clean
  checkout verification workflow passing at commit `8072c148` in
  [GitHub Actions run 35513104137](https://github.com/ANKOHR/veritydocs/actions/runs/35513104137).
- Public frontend: [`veritydocs-web.vercel.app`](https://veritydocs-web.vercel.app) returned HTTP
  200 and is backed by the `veritydocs-web` Vercel project rooted at `apps/web`.
- Public API: [`api-production-eb9c2.up.railway.app/health`](https://api-production-eb9c2.up.railway.app/health)
  returned `{"status":"ok","service":"veritydocs-api","environment":"production"}`.
  Railway deployment `fedc20b4-ac08-4d58-bbf6-eac4838ed78f` built commit `8072c148` from the
  repository Dockerfile. Startup logs recorded `ocr_engine=tesseract version=tesseract 5.5.0`.
- Railway bucket `veritydocs-documents` reported 16 objects and 11.1 MB after the proof runs.
  The valid source endpoint returned HTTP 200 with `application/pdf`; the rendered page endpoint
  returned HTTP 200 with `image/png`.
- Valid synthetic invoice proof: case `case_202412f21e97`, document `doc_b02e51dabf38`, fixture
  `invoice_inv_0042_scan.pdf`. The document completed as `invoice`; the extraction artifact
  contained `INV-0042`, `GBP`, net `8000.00`, tax `1600.00` and gross `9600.00`. The normalized
  artifact contained 32 OCR-token blocks with bounding boxes. `FIN-001` passed with expected and
  actual `9600`. The gross evidence points to page 1, text `9,600.00`, bbox `[247, 499, 338, 521]`.
- Inconsistent synthetic invoice proof: case `case_bf514a6e3769`, document `doc_29ef999527e5`,
  fixture `invoice_inv_0042_inconsistent_scan.pdf`. `FIN-001` failed with expected `9600` and
  actual `9900`; the case created an open review with reason `Validation FIN-001 failed: Gross
  does not equal net plus tax.` The gross evidence points to page 1, text `9,900.00`, bbox
  `[247, 499, 338, 521]`.
- Re-uploading each exact fixture returned `duplicate: true` with the original document ID.
  A different `X-Tenant-ID` received HTTP 404 for the case and evidence artifact endpoints.

The external run used `run_pipeline=true` so the proof could be completed without an unprovisioned
queue. It proves public API, object-storage, Docker/Tesseract, OCR-token provenance,
deterministic validation, duplicate detection and tenant-boundary behaviour. It does not prove a
durable Redis/Dramatiq worker or Postgres-backed deployment.

## Not claimed

- No real customer document has been processed.
- The OpenAI provider adapter is present but was not called because no API key was supplied or
  created.
- Tesseract was not available on the Windows host during the smoke test. The deployed Railway API
  image did exercise Tesseract, but this record does not claim a separate worker image or durable
  queued processing.
- Railway's free-plan resource limit blocked provisioning PostgreSQL, Redis and a separate worker
  in this account. The external proof used SQLite plus the synchronous API path; no live Postgres,
  Redis or Dramatiq deployment is claimed.
- No formal authentication, signed session/JWT boundary, malware scan, retention control or
  compliance certification/security audit is claimed.

## Reproduce the checks

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest -q
pnpm typecheck
pnpm build
.venv\Scripts\python.exe packages\evals\run_evals.py --write docs\eval-results.json
.venv\Scripts\alembic.exe upgrade head
```
