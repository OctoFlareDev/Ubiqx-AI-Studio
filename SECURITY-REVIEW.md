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
- Status: Mitigated.
- Detail: SVG can contain script. Assets are served with
  `Content-Disposition: attachment` (FileResponse default when a filename is
  set), and the HTML5 export references SVG via `<img>` elements, where
  embedded script does not execute.
- Residual risk: a user who downloads an SVG asset and opens it directly in a
  browser runs it in a local file context. Accepted for v1; a dedicated SVG
  sanitizer can be added later.

### 3. Unauthenticated bootstrap returns a wildcard key

- Severity: Medium if the service is exposed beyond localhost.
- Status: Accepted for local-first v1.
- Detail: `POST /api/v1/auth/bootstrap` creates/reuses the local user and
  returns an API key with the `*` scope, with no authentication. This is the
  intended first-run experience for a local app, but it must not be reachable
  from untrusted networks.
- Control: the service binds to localhost in development; per-key and per-IP
  rate limits (M5) bound unauthenticated bootstrap abuse.

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
- Status: Verified.
- Detail: keys are stored as salted SHA-256 hashes; plaintext keys are only
  returned once at creation. Scopes are validated against a known set and
  enforced per route (M5).

### 6. Upload validation and storage paths

- Severity: n/a.
- Status: Verified.
- Detail: uploads enforce extension, detected content signature, declared
  media type, and a size cap. Files are stored by content hash (hex path) in
  a fixed root, and original names are reduced to a basename, so path
  traversal is not possible.

### 7. Logging avoids secrets

- Severity: n/a.
- Status: Verified.
- Detail: structured request logs record method, path, status, duration, and
  request id only — no headers, bodies, or credentials. AI task errors log a
  stable code, not provider responses.

## Remaining Work

- Add a dedicated SVG sanitizer if SVG assets become a first-class export
  format (currently referenced, not inlined).
- Before any non-localhost deployment: require authentication for bootstrap,
  move SQLite to a managed store, and add per-tenant isolation.
