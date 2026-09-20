# Reliability and failure handling

The pipeline is designed to fail visibly:

- Exact duplicate submissions are idempotent through the case/hash uniqueness constraint.
- The worker boundary supports Dramatiq retries with a bounded three-attempt backoff policy.
- Processing stage and timings are persisted in `processing_runs`.
- Provider configuration errors fail closed; the API does not silently substitute an unconfigured
  live model.
- Missing source spans, missing fields, OCR limitations and cross-document disagreements can route
  to review or `UNABLE_TO_VERIFY`.
- Original source bytes and derived artifacts remain separate, allowing a future checkpoint/replay
  implementation without mutating the source.

The current implementation does not yet claim a production dead-letter dashboard, distributed
tracing, malware scanning or cloud object-storage durability. Those are the next reliability steps
after a real deployment target is authorized.
