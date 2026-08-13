# Ubiqx AI Studio Milestones

Status: Baseline for v1
Last updated: 2026-08-13

## Purpose

This file sequences the work into reviewable milestones. Each milestone has a deliverable, exit criteria, dependency, and checkpoint. Detailed per-milestone planning lives in `PLAN.md`, `PROGRESS.md`, and `WORKLOG.md`.

## Milestone Dependency Flow

M0 establishes the running system.
M1 proves the highest-risk import path.
M2 makes the imported scene editable.
M3 proves the core no-code delivery loop.
M4 adds asynchronous AI capability.
M5 makes the system available to agents.
M6 hardens and operates the result.

## M0 Walking Skeleton

Goal: Prove that the front end, back end, local project model, upload, autosave, CI, and Playwright can run together.

Deliverables:

- Monorepo and run scripts.
- Vue/Vite studio shell.
- FastAPI back end with generated OpenAPI.
- Minimal local auth.
- Local project CRUD.
- Validated file upload.
- Local autosave.
- Unit and Playwright smoke tests in CI.

Exit criteria:

- A clean checkout can start both services with documented commands.
- Project creation, listing, rename, archive, and delete work end to end.
- Allowed uploads succeed and invalid uploads fail with structured errors.
- Autosave persists across a front-end refresh.
- CI passes.

Primary risk: Settling the local-first development workflow and monorepo boundaries.

## M1 Structured Import

Goal: Prove that PSD/PSB can become a retained scene graph without losing primary structure.

Deliverables:

- PSD/PSB import adapter.
- Scene and scene-node models.
- Image asset extraction and content-addressed storage.
- Import job lifecycle and warnings.
- PNG, JPEG, WebP, and SVG import.
- Figma adapter stub or deferred implementation.

Exit criteria:

- Fixed PSD/PSB fixtures import with accepted hierarchy fidelity.
- Extracted assets are stable and deduplicated.
- Unsupported effects are preserved as metadata and included in warnings.
- Invalid and oversized files fail without corrupting project state.

Primary risk: PSD/PSB parser fidelity and behavior differences between fixtures.

## M2 Scene Graph and Canvas

Goal: Prove that the scene graph can be viewed and edited through CanvasKit without data loss.

Deliverables:

- Retained scene graph as source of truth.
- CanvasKit canvas.
- Selection, move, resize, zoom, and pan.
- Layers panel and properties panel.
- Undo/redo.
- Autosave integration.

Exit criteria:

- Canvas operations round-trip through the scene graph.
- Undo/redo restores previous state.
- Reload restores the same scene.
- Large previews use downsampling without changing source assets.

Primary risk: CanvasKit integration, large-asset memory use, and interaction edge cases.

## M3 HTML5 Export

Goal: Prove the v1 no-code delivery loop by producing a runnable HTML5 package.

Deliverables:

- HTML5 export adapter.
- Asset manifest and package validation.
- PNG, JPEG, WebP, and SVG asset export.
- Export preview.
- Export warning report.

Exit criteria:

- A non-empty scene exports as a self-contained package.
- The package opens in a current browser.
- Hierarchy and referenced assets are preserved within documented fidelity limits.
- Export validation runs before completion.

Primary risk: Choosing the right package format for hierarchy preservation and visual fidelity.

## M4 AI Asset Generation

Goal: Prove asynchronous, cancellable, cost-controlled AI work.

Deliverables:

- AI provider adapter interface.
- Local asynchronous task runner and persisted task state.
- Upscaling.
- Background removal or matting.
- Polling, cancellation, retry limits, and cost/usage tracking.

Exit criteria:

- Tasks have a complete observable lifecycle.
- Cancellation stops further retries.
- Provider failures exhaust retry budgets and then stop.
- Provider credentials remain server-side only.

Primary risk: Provider API differences, image quality, timeout behavior, and cost control.

## M5 Agent REST API

Goal: Prove that humans and future agents can use the same stable REST contract.

Deliverables:

- Committed generated OpenAPI contract.
- API key management and scopes.
- Rate limiting.
- Task polling.
- Contract tests.

Exit criteria:

- Generated contract is reproducible.
- Contract tests detect route and schema drift.
- Scoped API keys cannot access unauthorized resources.
- Rate limits return structured errors.

Primary risk: Schema instability during earlier milestones, causing contract churn.

## M6 Quality and Ops

Goal: Harden the product for release.

Deliverables:

- Visual regression tests.
- API contract tests.
- Security review.
- Performance smoke tests.
- Structured logging and readiness checks.
- Backup/restore and deployment runbook.

Exit criteria:

- Critical visual changes are caught by regression tests.
- Security findings are triaged and high-severity issues resolved.
- Large fixtures meet performance targets.
- Backup and restore are documented and verified.

Primary risk: Late discovery of security, memory, or operational gaps.

## Human Checkpoints

Each milestone closes with a human review before the next milestone starts. The review should check both the implementation and the updated milestone `PLAN.md`, `PROGRESS.md`, and `WORKLOG.md`.
