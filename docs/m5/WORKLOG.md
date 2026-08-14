# M5 Agent REST API Worklog

## 2026-08-14

- Added `apps/api/app/rate_limit.py` with a sliding-window limiter and opaque key derivation.
- Added `UBIQX_RATE_LIMIT` / `UBIQX_RATE_LIMIT_WINDOW_SECONDS` settings.
- Wired a rate-limit middleware that returns a structured `429` envelope for `/api/v1` routes.
- Added the scope model and `normalize_scopes` validation in `security.py`.
- Refactored `verify_api_key` to return the authenticated key alongside the user.
- Added `AuthContext` and `require_scope` dependencies in `deps.py`.
- Enforced per-route scopes across all 30 authenticated endpoints.
- Added API key create/list/revoke endpoints and `ApiKeyCreate/Read/Created/List` schemas.
- Added `scripts/generate_contract.py` and a `make contract` target.
- Regenerated and committed `packages/contracts/openapi.json`.
- Added contract drift, scope-enforcement, and rate-limit tests (34 tests green).
- Updated `API-CONTRACT.md` with API key routes, scopes, and rate limiting.

## Human checkpoint

Pending human review; no sign-off has been recorded yet.
