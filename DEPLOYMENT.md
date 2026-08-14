# Ubiqx AI Studio Deployment Runbook

Status: M6
Last updated: 2026-08-14

## Purpose

Operating procedures for running, observing, backing up, and restoring a
local Ubiqx AI Studio instance. v1 is local-first: FastAPI + SQLite + a
content-addressed asset store.

## Prerequisites

- Python 3.12+ (backend).
- Node.js 22+ (front end).
- `apps/api/requirements.txt` installed in an active environment.

## Run

Backend (from the repo root):

```bash
python -m uvicorn app.main:app --app-dir apps/api --port 8000
```

Frontend (from the repo root):

```bash
npm run dev:web
```

The frontend proxies `/api` to the backend in development. Production serving
builds the web app (`npm run build:web`) and serves `apps/web/dist` statically.

## Configuration

Environment variables (all optional for local use):

- `UBIQX_DATA_DIR` — data root (defaults to `apps/api/data`).
- `UBIQX_DATABASE_URL` — SQLAlchemy URL (defaults to SQLite under the data dir).
- `UBIQX_MAX_UPLOAD_BYTES` — upload cap (default 50 MiB).
- `UBIQX_RATE_LIMIT` / `UBIQX_RATE_LIMIT_WINDOW_SECONDS` — rate limits.
- `UBIQX_IDEMPOTENCY_RETENTION_SECONDS` — retry-response retention (default 24h).
- `UBIQX_AI_DAILY_COST_QUOTA` — rolling 24-hour AI cost allowance (default 10).
- `UBIQX_AI_MAX_CONCURRENT_TASKS` — per-user queued/running AI task cap (default 2).
- `UBIQX_AI_COST_PER_MEGAPIXEL` — normalized local usage rate (default 0.01).
- `UBIQX_ALLOW_REMOTE_BOOTSTRAP` — keep `0` (the default) unless a controlled
  deployment explicitly needs remote first-run bootstrap; remote clients are
  rejected otherwise.

## Readiness

- `GET /health` — liveness.
- `GET /ready` — checks the database plus writability of the asset, export,
  and temp directories; returns `200` with `status: ready` or `503` with
  `status: degraded`.

## Logging

Logs are one JSON object per line. Every request log includes a request id,
method, path, status, and duration. Import, export, and AI job runners emit
`*_started` / `*_succeeded` / `*_failed` / `*_cancelled` lines with the job or
task id. Logs never contain request bodies, headers, or provider credentials.

## Backup

```bash
python scripts/backup.py backup --out /path/to/ubiqx-backup.tar.gz
```

The archive contains a consistent SQLite snapshot (via the SQLite online
backup API) plus the asset store. Backup can run while the service is up.

## Restore

1. Stop the service.
2. Restore:

```bash
python scripts/backup.py restore /path/to/ubiqx-backup.tar.gz
```

3. Verify: `GET /ready` returns `200`; open a project and confirm its assets
   are present.
4. Start the service.

Restore is guarded against path-traversal entries in the archive.

On startup the API creates missing tables and applies additive schema
migrations recorded in the `schema_migrations` table. Project scene changes
also create immutable local recovery revisions, which can be listed and
restored through the project revisions API.

## Verification

```bash
python -m pytest apps/api/tests -q       # unit + integration + contract
npm run typecheck && npm run build:web   # frontend
bash scripts/run-e2e.sh                  # Playwright smoke + visual capture
```

Backup/restore is exercised by `apps/api/tests/test_ops.py`.
