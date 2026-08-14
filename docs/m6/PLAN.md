# M6 Quality and Ops Plan

Status: In progress

## Goal

Harden the product for release: contract coverage, security review and fixes,
performance smoke tests, structured logging and readiness, backup/restore, and
visual-regression scaffolding. Detailed visual parity review is deferred to a
vision model.

## Work Items

- [x] Structured JSON logging with request IDs and job/task lifecycle lines.
- [x] `/ready` checks database plus asset/export/tmp directory writability (503 when degraded).
- [x] Security review (`SECURITY-REVIEW.md`) with two fixes: export filename sanitization and zip-slip-safe restore.
- [x] Backup/restore (`ops.py` + `scripts/backup.py`) with round-trip and traversal tests.
- [x] Performance smoke tests (list 500 nodes, export 300 nodes within budgets).
- [x] Contract completeness test (documented resources present in OpenAPI).
- [x] Visual regression scaffolding (`tests/e2e/visual.spec.ts`) — pixel comparison deferred to a vision model.
- [x] Deployment runbook (`DEPLOYMENT.md`).
- [x] Removed a redundant duplicate `openProject` that caused upload flakiness in E2E.

## Verification

- `python -m pytest apps/api/tests -q`
- `npm run typecheck && npm run build:web`
- `bash scripts/run-e2e.sh`

## Checkpoint

Human review of security findings, backup/restore, and visual screenshots.
