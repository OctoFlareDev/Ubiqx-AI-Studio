# M6 Quality and Ops Progress

Status: Ready for human checkpoint

## Current State

- Logs are JSON, one object per line, with request IDs and import/export/AI job lifecycle lines.
- `/ready` returns 200 when DB + asset/export/tmp dirs are writable, else 503 `degraded`.
- `SECURITY-REVIEW.md` records findings; export filename sanitization and zip-slip-safe restore are fixed and tested.
- `scripts/backup.py backup/restore` snapshots SQLite + assets; `test_ops.py` covers round-trip and path-traversal rejection.
- Performance smoke tests assert 500-node list and 300-node export stay within budgets.
- Contract tests assert drift detection, reproducibility, and that documented resources exist.
- Visual regression captures imported/selected states with committed CanvasKit
  pixel baselines across Chromium, Firefox, and WebKit; full-page screenshot
  parity remains a human review item.
- `DEPLOYMENT.md` documents run, readiness, logging, backup, restore, and verification.

## Next

- Review `test-results/visual/*.png` and the committed CanvasKit baselines for
  intentional visual changes.
- Human review of security findings and the runbook.
