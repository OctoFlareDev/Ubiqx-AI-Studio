# Ubiqx AI Studio Security Review

Status: M6
Last updated: 2026-08-14

## Purpose

Records the v1 security review findings and their disposition. High-severity
items must be fixed; lower-severity items are documented as accepted or
mitigated with a rationale. The threat model is in `SECURITY-AND-OPS.md`.

## Findings

### 1. Export download filename derived from project name

- Severity: Low.
- Status: Fixed.
- Detail: `GET /api/v1/exports/{id}/download` built the `Content-Disposition`
  filename from the user-controlled project name. Starlette quotes the
  filename, but the name could still contain path separators or control
  characters.
- Fix: added `_safe_export_filename` in `main.py` to strip everything except
  alphanumerics and a small safe set before use.

### 2. SVG assets served as image/svg+xml

- Severity: Low (local-first).
- Status: Fixed.
- Detail: SVG uploads are parsed and sanitized before content-addressed
  storage. External links, event attributes, script-like elements, and unsafe
  styles are removed; malformed or entity-enabled documents are rejected.
- Residual risk: the sanitizer is intentionally conservative and does not
  promise pixel-perfect preservation of every SVG feature.

### 3. Unauthenticated bootstrap returns a wildcard key

- Severity: Medium if the service is exposed beyond localhost.
- Status: Mitigated for local-first v1.
- Detail: `POST /api/v1/auth/bootstrap` creates/reuses the local user and
  returns an API key with the `*` scope, with no authentication. This is the
  intended first-run experience for a local app, but it must not be reachable
  from untrusted networks.
- Control: the service binds to localhost in development; remote bootstrap is
  rejected unless `UBIQX_ALLOW_REMOTE_BOOTSTRAP=1` is explicitly set, and
  per-key/per-IP rate limits bound abuse.

### 4. Backup restore path traversal (zip-slip)

- Severity: Medium.
- Status: Fixed.
- Detail: `scripts/backup.py restore` extracts a tar archive. A malicious
  archive could write outside the data directory.
- Fix: `ops.py` validates every entry (rejects absolute paths and `..`) and
  passes `filter="data"` to `extractall`. Covered by
  `test_restore_rejects_path_traversal`.

### 5. API key storage

- Severity: n/a.
- Status: Fixed and verified.
- Detail: keys are stored with a per-key random salt and PBKDF2-HMAC-SHA256;
  plaintext keys are only returned once at creation. Legacy unsalted records
  are migrated on successful verification. Scopes are validated against a
  known set and enforced per route.

### 6. Upload validation and storage paths

- Severity: n/a.
- Status: Fixed and verified.
- Detail: uploads enforce extension, detected content signature, declared
  media type, and a size cap; record dimensions and detection metadata; clean
  temporary files on duplicate and failed writes; and sanitize SVG content.
  Files are stored by content hash in a fixed root, and original names are
  reduced to a basename.

### 7. Logging avoids secrets

- Severity: n/a.
- Status: Verified.
- Detail: structured request logs record method, path, status, duration, and
  request id only — no headers, bodies, or credentials. AI task errors log a
  stable code, not provider responses.

### 8. Scene graph integrity and recovery

- Severity: High before M6 fixes.
- Status: Fixed and covered.
- Detail: scene mutations validate same-scene parents, reject cycles, protect
  root nodes, use optimistic versions/ETags, and create immutable project
  revisions. The API exposes revision listing and restore with `If-Match`.

### 9. Idempotent mutation retries

- Severity: Medium.
- Status: Fixed and covered.
- Detail: mutation requests with an `Idempotency-Key` are scoped to the
  credential and route, retain successful responses for a configurable window,
  replay identical requests, and reject payload changes.

## Remaining Work

- Before any non-localhost deployment: require authentication for bootstrap,
  move SQLite to a managed store, and add per-tenant isolation.
