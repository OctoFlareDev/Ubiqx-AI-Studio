# Ubiqx AI Studio Test Plan

Status: Baseline for v1
Last updated: 2026-08-13

## Purpose

This file defines the testing strategy and exit gates for v1. It is not a replacement for per-milestone plans, but it establishes the common test pyramid and fixtures.

## Test Pyramid

```text
E2E / visual regression
Integration and API contract tests
Unit tests
```

Most logic is covered by unit and integration tests. E2E tests cover the primary user loop and are intentionally small in number.

## Test Levels

### Unit Tests

Owners: front-end and back-end developers.

Scope:

- Scene graph invariants and node operations.
- Transform and ordering calculations.
- Import parser normalization.
- Export adapter logic.
- AI provider response normalization.
- Auth and scope checks.
- Autosave scheduling.

### Integration Tests

Scope:

- SQLite persistence.
- Content-addressed asset storage.
- Import-to-scene-graph flow.
- Scene mutation to autosave flow.
- HTML5 export to package validation flow.
- AI task lifecycle with a fake provider.

### API Contract Tests

Scope:

- Generate OpenAPI from the running app.
- Compare it against the committed contract.
- Exercise success and error response schemas.
- Verify status-code mappings.

### E2E Playwright Tests

Scope:

- Create project.
- Upload fixture.
- Import fixture.
- Open canvas.
- Move a node.
- Reload and confirm state.
- Export HTML5 package.
- Create and poll a fake AI task.

### Visual Regression Tests

Scope:

- Empty project state.
- Imported fixture canvas.
- Selected node state.
- Hidden and locked node state.
- HTML5 export preview.

Use deterministic fixtures and recorded screenshots. Ignore only expected anti-aliasing or rendering differences.

## Fixtures

Repository fixtures must include:

- Small valid PSD with groups, text, shapes, and image layers.
- Small valid PSB.
- PSD with layer effects that cannot be rendered perfectly.
- Oversized image requiring downsampling.
- Malformed PSD.
- PNG, JPEG, WebP, and SVG samples.
- Transparent PNG for background removal.
- Low-resolution image for upscaling.

Fixtures should not require proprietary licensed content.

## AI Test Strategy

Production AI calls are not deterministic enough for core tests.

- Unit and integration tests use a fake provider adapter.
- The fake provider can succeed, fail, time out, and reject cancellation.
- A small manual or opt-in provider smoke suite validates real credentials and output quality.
- AI quality gates include human review of fixed input sets.

## CI Stages

1. Lint and typecheck.
2. Unit tests.
3. Integration tests.
4. API contract tests.
5. Build artifacts.
6. Playwright smoke tests.
7. Visual regression.
8. Security and secret scans.

## Failure Handling

- Flaky tests are tracked and fixed, not silently disabled.
- Provider-dependent tests must be skipped when credentials are unavailable.
- Visual baselines are reviewed on every intentional change.

## Exit Gates

A milestone closes only when:

- Its acceptance criteria pass.
- New functionality has appropriate automated coverage.
- CI passes on a clean checkout.
- Manual checkpoint notes are recorded in the milestone worklog.
