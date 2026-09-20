# VerityDocs architecture

VerityDocs is a document-processing system, not a document chatbot. The durable unit of work is
an immutable source document belonging to a tenant-scoped case.

```text
Next.js case workspace
        |
        v
FastAPI API ---- PostgreSQL metadata/facts
        |\
        | \---- S3-compatible object-store boundary
        |
        +---- Redis/Dramatiq queue
                    |
                    v
          normalize -> OCR -> classify -> extract
                    -> validate -> reconcile
                    -> confidence -> human review
```

## Data flow

1. `POST /api/cases/{id}/documents` reads the upload, validates the extension/size, computes a
   SHA-256 and stores the original bytes under an immutable object key.
2. Normalization converts native PDF text, rendered PDF pages, XLSX sheets, CSV files and images
   into `NormalizedDocument` pages containing text blocks, tables, image artifacts and optional
   bounding boxes.
3. The OCR adapter is invoked only when a page has no native text. Native text and spreadsheet
   inputs therefore do not depend on an OCR binary. Docker installs Tesseract for image-only
   documents; if it is unavailable, the pipeline records the limitation and keeps the extracted
   value reviewable rather than inventing text.
4. A provider returns a Pydantic classification and typed extraction. `DemoExtractionProvider` is
   deterministic and credential-free. `OpenAIMultimodalProvider` uses structured JSON schema
   output but raises `ProviderNotConfigured` without an explicit key.
5. Each top-level field is persisted with the provider/model method, extraction score, OCR score,
   validation state and one or more evidence references. The original file is never overwritten.
6. Validation rules are ordinary Python. Reconciliation compares compatible facts across source
   documents. Conflicts and unsupported claims remain visible and can create review items.

## Storage boundary

PostgreSQL stores normalized metadata, typed values, review decisions, rule outcomes and audit
events. `LocalObjectStore` is the local implementation of the object-storage interface; a future
S3-compatible implementation can replace it without changing the pipeline contract. Derived
artifacts are separate from originals:

```text
documents/{document_id}/original/<filename>
documents/{document_id}/rendered/page-001.png
documents/{document_id}/normalized.json
documents/{document_id}/extraction.json
```

## Provider boundary

The application defaults to `EXTRACTION_PROVIDER=demo` so the seeded case and tests are
reproducible without external credentials. To exercise a real provider later, configure the
provider in a private environment and keep the resulting evidence separate from the synthetic
benchmark. No OpenAI call is made by the current local run.

## Deployment shape

`docker-compose.yml` provides API, worker, PostgreSQL and Redis. The API can process a demo upload
synchronously; setting `run_pipeline=false` uses Redis/Dramatiq when `REDIS_URL` is present, and
falls back to a local background task for development when it is not. Alembic contains the initial
schema migration; the API's `create_all` startup path is a development convenience.
