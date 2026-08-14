# M5 Agent REST API Plan

Status: In progress

## Goal

Prove that humans and future agents use the same stable REST contract with
scope-restricted keys, rate limits, task polling, and a reproducible committed
OpenAPI document.

## Work Items

- [x] Add a sliding-window rate limiter with configurable limits and a structured `429` envelope.
- [x] Add scope model (`projects/assets/scenes/imports/exports/ai/api_keys` read+write, plus `*`).
- [x] Refactor auth to return the authenticated key and enforce scopes on every route.
- [x] Add API key management endpoints (create, list, revoke) restricted to `api_keys:*`.
- [x] Add a reproducible contract generation script and `make contract` target.
- [x] Add contract drift, scope-enforcement, and rate-limit tests.
- [x] Regenerate and commit `packages/contracts/openapi.json`.
- [x] Update `API-CONTRACT.md`.

## Verification

- `make test-api`
- `make contract`

## Checkpoint

Human review of scope enforcement, rate limiting, and the committed contract.
