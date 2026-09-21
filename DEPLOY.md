# Railway demo deployment

This is the shortest path to a shareable demo link for the local invoice-checker page. It uses the
repository's existing Dockerfile and intentionally keeps the default SQLite and local storage
backends. That is suitable for a disposable demo, not for durable production data.

## 1. Create the service

1. Create a new Railway project and choose **Deploy from GitHub repo**.
2. Select `ANKOHR/veritydocs` and the `main` branch.
3. Keep the repository root as the service root. The checked-in `railway.json` selects the
   Dockerfile builder and `/health` health check.

The FastAPI service is self-contained. The existing Next.js app in `apps/web` is not required for
this demo.

## 2. Set only these variables

```text
APP_ENV=production
OCR_ENGINE=tesseract
EXTRACTION_PROVIDER=demo
```

Do not add `DATABASE_URL`, S3 variables, or `REDIS_URL` for this demo. The application defaults to
SQLite, local file storage, synchronous processing, and the deterministic demo extraction provider.
Railway supplies `PORT`; the Dockerfile binds to `0.0.0.0` and uses `${PORT:-8000}`.

## 3. Verify the live service

After Railway reports a successful deployment, open:

- `/health`: should return JSON containing `"status": "ok"`.
- `/demo`: should show the invoice validation page.

Run all three sample cards:

- **Clean sample**: `PASS`, calculated gross £9,600, observed gross £9,600.
- **Totals mismatch**: `FAIL`, expected £9,600, observed £9,900, discrepancy £300.
- **Missing field**: `UNABLE TO VERIFY`, rule `FIN-001`.

The Dockerfile installs Tesseract and starts the API with:

```text
uvicorn veritydocs_api.main:app --app-dir apps/api --host 0.0.0.0 --port ${PORT:-8000}
```

The local SQLite database and storage directory are ephemeral on Railway. Add a durable database,
object storage, or a worker service only if this demo later becomes a production application.
