# Invoice-checker demo build notes

## Existing components reused

- `apps/api/veritydocs_api/main.py` remains the FastAPI entry point and existing API surface.
- `apps/api/veritydocs_api/service.py::process_document` is the real document processing entry
  point used by the demo upload flow through `POST /api/cases/{case_id}/documents`.
- `apps/api/veritydocs_api/pipeline/normalize.py::normalize_document` handles PDF and image
  normalization and rendered page artifacts.
- `apps/api/veritydocs_api/pipeline/ocr.py::TesseractOCREngine` and
  `enrich_page_with_ocr` provide the existing Tesseract boundary and OCR evidence tokens.
- `apps/api/veritydocs_api/providers.py::DemoExtractionProvider` performs the existing
  credential-free deterministic classification and invoice extraction.
- `apps/api/veritydocs_api/validation.py::validate_document` supplies the existing `FIN-001`
  arithmetic rule and its `PASS`, `FAIL`, and `UNABLE_TO_VERIFY` outcomes.
- `apps/api/veritydocs_api/service.py::case_view` supplies extracted fields, validation rows,
  field confidence, and source evidence in the existing `CaseView` schema.
- `apps/api/veritydocs_api/storage.py::LocalObjectStore` is used by the API in local development.

## Existing synthetic-data tooling reused

`scripts/generate_invoice_fixtures.py` remains the source for the image-only invoice PDFs. It now
also creates `fixtures/invoice_inv_0042_missing_tax_scan.pdf` by omitting the VAT line while keeping
the real invoice fields and validation boundary unchanged. The original clean and mismatch
fixtures remain unchanged in the working tree.

## New demo-specific components

- `apps/api/veritydocs_api/demo.py` adds the `/demo` HTML page and a safe, allow-listed route for
  the three bundled sample PDFs.
- The page uses plain HTML, CSS, and browser JavaScript. It creates a local case, uploads the file
  through the existing API endpoint with `run_pipeline=true`, then fetches the existing case view.
- The presentation adapter renders the actual extracted fields, validation identifiers and
  statuses, expected/calculated values, observed values, numeric discrepancy when both values are
  available, and source-span evidence returned by the pipeline.
- `apps/api/tests/test_demo.py` adds focused checks for the page contract and the three real sample
  outcomes.

## Deliberate simplifications and boundaries

- Each demo run creates one fresh local case containing one document. It does not add a new
  persistence model or change existing validation semantics.
- The page is intentionally invoice-focused. It offers PDF and image upload even though the
  existing API also accepts spreadsheets for the broader case workspace.
- The demo uses the existing default development tenant and does not add authentication.
- The page does not implement review resolution, cross-document reconciliation, or the existing
  Next.js case workspace. Those remain available through the original API and web application.
- `InvoiceExtraction` includes a `line_items` field in the existing schema, but the current demo
  provider does not populate it. The page displays the fields the pipeline actually returns and
  does not invent line-item extraction.
- The missing-field sample omits VAT. This is a field the existing invoice provider genuinely
  extracts and the existing `FIN-001` validator genuinely requires, so its result is
  `UNABLE_TO_VERIFY` rather than a new demo-only rule.

No external service, account, deployment, commit push, or remote repository change was made.
