# Security boundary

VerityDocs handles document-shaped data that may be sensitive. The current local implementation
demonstrates the following controls:

- Cases carry a `tenant_id`; every case, document, review and case view is resolved through that
  tenant boundary.
- Original files are stored outside the relational database behind an object-store abstraction.
- Download endpoints check ownership before returning a source or rendered page artifact.
- Uploads have an allow-list of document extensions, a 25 MiB limit and immutable SHA-256 identity.
- Provider credentials are server-side settings only. The frontend never receives an API key.
- Human corrections are additive review decisions and audit events, not silent replacement of the
  original machine extraction.
- A malformed structured provider response cannot enter the typed extraction path because Pydantic
  validation is required before persistence.

Before production use, add signed short-lived object URLs, malware scanning, a managed secret store,
rate limiting, retention policies, formal authentication and an external security review. Those
items are intentionally not represented as completed here.
