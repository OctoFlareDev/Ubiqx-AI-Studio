# M4 AI Asset Generation Plan

Status: Ready for human checkpoint

## Goal

Prove asynchronous, cancellable, retry-limited AI asset processing while keeping provider credentials server-side.

## Work Items

- [x] Commit the M3 HTML5 export baseline.
- [x] Add `AiTask` persistence and REST lifecycle.
- [x] Add a provider adapter interface.
- [x] Add the local image provider with upscaling and background removal.
- [x] Add polling, cancellation, retry limits, backoff, and usage tracking.
- [x] Add front-end AI processing actions.
- [x] Add AI task tests and regenerate the OpenAPI contract.
- [x] Run final verification and record the human checkpoint.

## Verification

- `/tmp/ubiqx-venv/bin/python -m pytest apps/api/tests -q`
- `npm run typecheck`
- `npm run build:web`
- `npx playwright test`

## Checkpoint

Human review of local upscaling and background removal results.
