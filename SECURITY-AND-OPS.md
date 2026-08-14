# Ubiqx AI Studio Security and Ops

Status: Baseline for v1
Last updated: 2026-08-13

## Purpose

This file records the v1 security model, operational expectations, and incident response baseline. v1 is local-first, so the highest risks are malicious or malformed design files, secret leakage, and uncontrolled AI costs.

## Threat Model

### File Import Threats

- Malformed PSD/PSB causing parser crashes or excessive memory use.
- Upload path traversal.
- Polyglot files bypassing declared MIME type.
- Compressed or nested content causing decompression exhaustion.

### API Threats

- Missing or bypassed authorization.
- API key leakage or plaintext storage.
- Stale scene mutations overwriting newer edits.
- Unbounded uploads or list responses.

### AI Threats

- Prompt or metadata exfiltration through provider requests.
- Provider credentials exposed to the browser.
- Uncontrolled retry spend.
- User content sent to unapproved providers.

### Local App Threats

- Malicious files opening in a browser context.
- Local secrets committed to the repository.
- Loss of local project data without recovery.

## Security Controls

### Upload and File Handling

- Enforce a maximum upload size.
- Validate extension, declared MIME, detected type, and expected content signature.
- Reject paths, device names, and unusual path separators.
- Store files by content hash in a fixed root.
- Limit decompression and parser resources.
- Treat imported files as untrusted throughout the pipeline.

### Auth and Secrets

- Store API keys as salted hashes.
- Use local session or bearer key for every mutating request.
- Resolve provider credentials only on the backend.
- Read secrets from environment variables or a git-ignored local secret file.
- Do not log provider keys, tokens, or full request bodies.

### Scene Mutation Integrity

- Mutations include a scene or node version when optimistic concurrency matters.
- Reject stale mutations with `409`.
- Keep a latest `ProjectRevision` for recovery.

### AI Cost and Retry Controls

- Enforce per-operation retry limits.
- Cap task concurrency.
- Record normalized usage and provider errors.
- Require explicit user action for expensive operations.
- Never automatically retry cancelled tasks.

## Operations

### Local Execution

- Back end runs as a local service.
- Front end runs through Vite in development.
- Metadata is in SQLite.
- Assets are in a content-addressed store.
- Autosave is local and idempotent.

### Observability

- Every request gets a request ID (echoed in the `X-Request-ID` response header).
- Every job and task gets a task ID and emits structured lifecycle log lines.
- Logs are JSON, one object per line, and avoid sensitive data (no bodies, headers, or credentials).
- `GET /health` is liveness; `GET /ready` checks the database and storage directory writability.

### Backup and Recovery

- Back up SQLite and the asset store together via `python scripts/backup.py backup --out <archive>`.
- Restore with `python scripts/backup.py restore <archive>` (service stopped).
- Restore procedure:
  1. Stop the service.
  2. Run the restore command.
  3. Verify `GET /ready` and project assets.
  4. Start the service.
- Restore rejects path-traversal archive entries.
- See `DEPLOYMENT.md` for the full runbook.

### Deployment Readiness

For a future cloud deployment:

- Move SQLite behind a managed or replicated database.
- Move asset storage to object storage.
- Replace the local task runner with a durable queue.
- Add central secret management.
- Add tenant isolation and stronger user identity.
- Keep the REST contract stable while changing these internals.

## Incident Response

For a suspected secret leak:

1. Revoke or rotate affected keys.
2. Identify exposure in logs and artifacts.
3. Remove the secret from history where possible.
4. Record the incident and prevention change.

For a malicious file:

1. Isolate the file.
2. Replicate the parser failure with a sanitized sample.
3. Fix the validation or parser path.
4. Add a regression fixture.

For unexpected AI spend:

1. Pause task creation for the affected scope.
2. Audit task and usage records.
3. Correct the retry, quota, or provider configuration.
4. Re-enable with a lower limit.

## Review Checklist

Before a v1 release:

- No high-severity security findings remain. (M6: see `SECURITY-REVIEW.md`; two low/medium issues fixed.)
- Upload and parser paths are covered by malicious-fixture tests.
- API keys and provider credentials are not stored in plaintext.
- Retry and cost controls are verified.
- Backup and restore has been tested. (M6: `test_ops.py` round-trip + traversal rejection.)
- Structured logs and readiness checks are present. (M6: JSON logs + request/job IDs + `/ready` storage checks.)
- The OpenAPI contract and deployed API match. (M6: contract drift + completeness tests.)
