# M5 Agent REST API Progress

Status: Ready for human checkpoint

## Current State

- A sliding-window rate limiter returns a structured `429 rate_limited` envelope on `/api/v1` routes.
- Every authenticated route declares required scopes; keys without a matching scope (or `*`) receive `403 insufficient_scope`.
- API keys can be created (with validated scopes), listed, and revoked through `api_keys:*` endpoints.
- Revoked keys immediately stop authenticating.
- Task polling (imports, exports, AI tasks) is covered by `*:read` scopes and terminal-status polling.
- A `make contract` script regenerates `packages/contracts/openapi.json` deterministically.
- Contract tests assert the running app matches the committed OpenAPI and that generation is reproducible.
- Full API suite passes (34 tests).

## Next

- Human review of scope enforcement, rate limits, and the committed contract.
