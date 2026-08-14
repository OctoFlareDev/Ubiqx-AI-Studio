# M6 Quality and Ops Worklog

## 2026-08-14

- Added `apps/api/app/logging.py` (JSON formatter + `configure_logging`).
- Added request logging middleware (method, path, status, duration_ms, request_id).
- Added job/task lifecycle log lines to import, export, and AI runners.
- Enhanced `/ready` to check database and asset/export/tmp directory writability.
- Sanitized the export download filename (`_safe_export_filename`).
- Added `apps/api/app/ops.py` (backup/restore with zip-slip protection) and `scripts/backup.py`.
- Added `test_ops.py`, `test_performance.py`, and contract completeness coverage.
- Added `tests/e2e/visual.spec.ts` (visual capture scaffolding).
- Wrote `SECURITY-REVIEW.md` and `DEPLOYMENT.md`; updated `SECURITY-AND-OPS.md`.
- Removed a redundant duplicate `openProject` in `StudioWorkspace.vue` that caused intermittent E2E upload flakes.
- Verified API tests, typecheck, web build, and the Playwright E2E suite across
  Chromium, Firefox, and WebKit. Added committed CanvasKit baselines for the
  imported and selected states.
- Regenerated `packages/contracts/openapi.json`.

## Human checkpoint

Pending human review; no sign-off has been recorded yet.
