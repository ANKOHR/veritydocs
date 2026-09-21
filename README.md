# VerityDocs: Evidence-backed document intelligence and reconciliation

Evidence-backed document intelligence for turning messy PDFs, scans and spreadsheets into
structured, validated and reviewable records.

> External proof status (2026-09-20): a public Vercel dashboard and Railway API are live. A
> synthetic image-only invoice was uploaded to the API, persisted in Railway's S3-compatible
> bucket, processed by Dockerized Tesseract 5.5.0, extracted with the credential-free
> deterministic provider, validated in Python and exposed with page/bounding-box evidence. A
> deliberately inconsistent invoice produced `FIN-001: FAIL` and an open review. This proof
> uses the synchronous `run_pipeline=true` path: Railway's free-plan resource limit prevented
> provisioning Postgres, Redis and a separate worker, so those services are not claimed here.
> No live provider key, real customer document or real-world accuracy claim is included.

VerityDocs is intentionally not a document chatbot. Its central object is a document pipeline:

```text
immutable upload
  -> PDF/image/spreadsheet normalization
  -> OCR and layout representation
  -> typed extraction
  -> field-level provenance
  -> deterministic validation
  -> cross-document reconciliation
  -> composite confidence
  -> human review or VERIFIED output
```

## Local invoice-checker demo

This repository includes a small FastAPI page at `/demo`. It accepts an invoice PDF or image and
uses the existing VerityDocs normalization, Dockerized-Tesseract-compatible OCR adapter,
deterministic demo extraction provider, field evidence, and financial validation pipeline. The
page presents the actual `CaseView` returned by the API in a compact invoice-focused layout.

### Prerequisites

- Windows PowerShell, Python 3.13, and Git.
- Tesseract OCR 5.x on `PATH` for the bundled image-only invoice samples. The repository
  Dockerfile installs `tesseract-ocr` and `tesseract-ocr-eng` for container runs.
- Node.js and pnpm are only needed for the existing Next.js case workspace, not for this FastAPI
  demo page.

### Install and run the FastAPI demo

From the repository root:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m uvicorn veritydocs_api.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/demo](http://127.0.0.1:8000/demo). The page has a local-file upload
path and three clearly labelled synthetic samples:

- `Clean sample` uses the existing `£8,000.00` net and `£1,600.00` VAT values with a `£9,600.00`
  gross total and should pass `FIN-001`.
- `Totals mismatch sample` uses the same inputs with a stated `£9,900.00` gross total and should
  expose the existing `FIN-001` failure and a `£300.00` discrepancy.
- `Missing field sample` omits VAT from the synthetic document. The existing validator should
  return `FIN-001` as `UNABLE_TO_VERIFY` because the arithmetic inputs are incomplete.

The demo creates a fresh local case for each run and calls the existing API upload endpoint with
`run_pipeline=true`. It does not call an external service or modify the remote repository.

### Tests

Run the backend suite, including the focused demo integration checks, with:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

The fixture generator can recreate the three invoice PDFs with:

```powershell
.venv\Scripts\python.exe scripts\generate_invoice_fixtures.py
```

If Tesseract is not available, the existing pipeline fails closed for image-only input and the
sample results cannot be treated as OCR verification. Native-text PDFs and the rest of the
backend tests remain separate from that system dependency.

The first showcase case is **Acme Property Acquisition**. It combines a rent roll, operating
statement, loan summary and property-tax record. The case view exposes reconciled financial facts,
exceptions and source evidence for every important field.

## What is implemented

- FastAPI + SQLAlchemy relational data model with tenant-scoped cases, immutable document hashes,
  processing runs, artifacts, fields, evidence, validations, reconciliations, reviews and audit
  events.
- PDF native-text extraction and page rendering; XLSX/CSV table normalization with title rows,
  merged-cell-friendly offsets and totals-row handling; image normalization.
- Tesseract OCR adapter with a fail-closed unavailable-engine boundary and two public synthetic
  scanned-invoice fixtures.
- Credential-free deterministic fixture provider plus a structured OpenAI multimodal adapter that
  is never instantiated without an explicit key.
- Source-level field provenance, deterministic finance rules, cross-document reconciliation,
  composite confidence, human review and `UNABLE_TO_VERIFY` outcomes.
- Invoice extraction with VAT arithmetic and a contract/payment-application comparison path that
  surfaces a claimed amount above the agreement value as a conflict.
- Next.js evidence-first case workspace with source-region highlighting and a Docker Compose
  topology for API, worker, PostgreSQL and Redis.
- 49 targeted backend tests, a 100-case synthetic evaluation runner, Alembic initial migration and honest
  evidence documentation.

## Current implementation boundary

- Native PDF text extraction uses PyMuPDF.
- XLSX and CSV normalization handles title rows, merged cells, header offsets and totals rows.
- Scanned-page OCR uses a real Tesseract adapter when the binary is available; unavailable OCR
  fails closed and routes the document toward review.
- `DemoExtractionProvider` makes the fixture case reproducible without credentials.
- `OpenAIMultimodalProvider` is implemented as a structured-output adapter but is not called unless
  `EXTRACTION_PROVIDER=openai` and a separately configured key are present.
- `S3ObjectStore` is implemented for Railway's S3-compatible bucket; local development defaults to
  `LocalObjectStore`.
- The deployed proof uses the Railway API's Docker image and S3-compatible bucket. The public
  dashboard is deployed to `https://veritydocs-web.vercel.app` and the API health endpoint is
  `https://api-production-eb9c2.up.railway.app/health`.
- Every persisted field carries confidence, method, validation state and evidence references.
- Arithmetic and reconciliation rules are deterministic Python, never model-generated math.

No live model, customer result or production accuracy claim is made by the local fixture metrics.

## Run locally

```powershell
cd C:\Users\henry\veritydocs
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m uvicorn veritydocs_api.main:app --app-dir apps/api --reload
```

In another terminal:

```powershell
cd C:\Users\henry\veritydocs
pnpm install
pnpm --filter veritydocs-web dev
```

Open `http://localhost:3000`, load the seeded Acme case, and inspect the evidence-backed case
view. The case workspace also accepts a synthetic scanned invoice upload and polls the worker
until OCR, deterministic extraction and validation complete. Run the backend checks with:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe packages\evals\run_evals.py
```

To exercise the production-shaped local topology once Docker is available:

```powershell
docker compose up --build
```

The API is then at `http://localhost:8000`, the OpenAPI document is at `/docs`, and the worker
consumes `run_pipeline=false` uploads through Redis/Dramatiq. The default Compose provider remains
the deterministic fixture provider.

## API entry points

```text
GET  /health
POST /api/cases
GET  /api/cases
GET  /api/cases/{case_id}
POST /api/cases/{case_id}/demo-seed
POST /api/cases/{case_id}/contract-seed
POST /api/cases/{case_id}/documents
GET  /api/documents/{document_id}/pages/{page_number}
GET  /api/documents/{document_id}/processing
GET  /api/documents/{document_id}/artifacts/{kind}
GET  /api/review
POST /api/review/{review_id}/resolve
```

The `X-Tenant-ID` header selects the local tenant boundary; the default development tenant is
`demo-tenant`. Formal authentication is a production follow-up, not a claim of this local build.

See [`docs/architecture.md`](docs/architecture.md) and [`docs/evidence.md`](docs/evidence.md) for
the design and current claim boundary.
