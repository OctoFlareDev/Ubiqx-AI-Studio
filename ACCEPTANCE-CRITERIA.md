# Ubiqx AI Studio Acceptance Criteria

Status: Baseline for v1
Last updated: 2026-08-13

## Purpose

This file defines the observable conditions that must be true for each milestone to close. It is the implementation-side check for the product goals in `PRD.md`.

## Cross-Cutting Definition of Done

V1 is not done until all of the following are true:

- A PSD/PSB file imports without losing the primary scene hierarchy.
- A canvas operation round-trips through the scene graph without data loss.
- The HTML5 export opens in a browser and renders the expected scene and assets.
- An AI task reports status, supports cancellation, and never retries indefinitely.
- REST API operations match the generated OpenAPI contract.
- Core tests pass in CI, including at least one Playwright smoke path.

Every milestone must also include its own `PLAN.md`, `PROGRESS.md`, and `WORKLOG.md` under a milestone directory.

## M0 Walking Skeleton

Given a clean local environment, when the developer starts the front end and back end, then:

- The browser loads the studio shell.
- The API health endpoint returns success.
- The OpenAPI document is generated and available.
- The developer can create, list, rename, archive, and delete a local project.
- The developer can upload an allowed file and receive a validated asset.
- The application creates or reuses a local user profile and API key.
- Project changes are autosaved locally.
- Unit tests and a Playwright smoke test pass in CI.

## M1 Structured Import

Given a representative PSD/PSB fixture, when the user imports it, then:

- The import succeeds and reports a job result.
- The scene graph preserves document bounds and the primary layer/group hierarchy.
- Names, visibility, opacity, and transforms are preserved for primary layers.
- Image assets are extracted and stored exactly once by content hash.
- Text layers retain editable text and basic typography metadata where present.
- Unsupported effects are reported as warnings or metadata, not silently discarded.

Given a malformed or oversized file, when the user attempts import, then:

- The API returns a structured validation error.
- No partial scene becomes the active project scene.
- The original file is not corrupted or deleted.

## M2 Scene Graph and Canvas

Given an imported scene, when the user selects and moves a node, then:

- The canvas updates.
- The properties panel updates.
- The scene graph mutation is persisted or autosaved.
- Undo restores the previous transform.

Given a selected node, when the user resizes, changes opacity, renames, hides, or locks it, then:

- The operation affects only the selected node or intended group.
- Reloading the project restores the same scene state.
- Layer order remains stable when no ordering action is taken.

Given a large scene, when the user zooms or pans, then:

- The viewport responds without a page reload.
- Preview assets are downsampled when necessary without changing source assets.

## M3 HTML5 Export

Given a project with a non-empty scene graph, when the user exports HTML5, then:

- The export produces a self-contained package.
- The package opens in a current browser.
- The visible hierarchy and referenced assets match the source scene within documented fidelity limits.
- The package includes or references PNG, JPEG, WebP, or SVG assets as expected.
- Export validation passes before the job is marked complete.

Given a node using an unsupported visual effect, when the user exports, then:

- The export completes.
- The unsupported effect is documented in a warning report.
- No unrelated node or asset is omitted.

## M4 AI Asset Generation

Given an AI upscaling or background-removal request, when the user creates it, then:

- The API returns an AI task with a unique ID and an initial status.
- Polling returns one of `queued`, `running`, `succeeded`, `failed`, or `cancelled`.
- A successful task creates or updates the expected asset.
- A failed task includes a non-sensitive structured error.

Given a long-running AI task, when the user cancels it, then:

- The task transitions to `cancelled`.
- The provider is not billed for unnecessary continued work where cancellation is supported.
- The system never retries a cancelled task.

Given a provider failure, when retries are exhausted, then:

- The task transitions to `failed`.
- Retry count and last error are recorded.
- No further automatic retry occurs.

## M5 Agent REST API

Given the running API, when the OpenAPI contract is generated, then:

- The contract is committed and reproducible.
- The contract includes project, asset, scene, node, import, export, and AI task operations.
- Contract tests fail if a route or response schema drifts.

Given an API key with project scope, when an agent calls a scoped endpoint, then:

- Allowed operations succeed.
- Disallowed operations return `403`.
- Rate limits are enforced with a structured `429` response.

## M6 Quality and Ops

Given a code change, when CI runs, then:

- Unit, integration, contract, and smoke tests run.
- Visual regression detects unintended canvas changes.
- Security and secret scans run.
- The release artifact is buildable.

Given a deployed or local production-like instance, when an operator checks it, then:

- Health and readiness endpoints reflect real dependencies.
- Logs include request IDs and task IDs.
- Restore can rebuild the SQLite metadata and asset store from backup.

## Human Checkpoints

- M0: Review the walking skeleton and agree that the local-first workflow is usable.
- M1: Review imported PSD/PSB fixtures for primary hierarchy fidelity.
- M2: Review canvas interactions and undo/redo behavior.
- M3: Open the HTML5 export in a browser and verify visual parity.
- M4: Review AI results and provider cost controls.
- M5: Review the OpenAPI contract and agent-facing usage.
- M6: Review security, performance, and deployment readiness before v1 release.
