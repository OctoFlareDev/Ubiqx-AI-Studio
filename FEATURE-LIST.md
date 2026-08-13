# Ubiqx AI Studio Feature List

Status: Baseline for v1
Last updated: 2026-08-13

## Purpose

This file is the feature backlog for Ubiqx AI Studio. It is organized by milestone and by priority. The PRD is the product intent; this file is the buildable feature surface.

## Priority Labels

- `P0`: Required for the current milestone.
- `P1`: Important v1 capability.
- `P2`: Valuable, but deferrable within v1.
- `Future`: Explicitly outside v1.

## M0 Walking Skeleton

### P0

- Monorepo with separate front-end and back-end packages.
- Vue/Vite front-end shell with the three-panel studio layout.
- FastAPI back-end with health, OpenAPI, and JSON error envelopes.
- Minimal local authentication with a persistent local user profile and API key.
- Local project create, read, update, list, archive, and delete.
- File upload with size, MIME, and extension validation.
- Project listing and empty project state.
- Local project autosave service.
- CI pipeline with unit tests and a Playwright smoke test.

### P1

- Basic navigation between project list and studio workspace.
- Project rename and archive.
- Shared TypeScript API client generated from the OpenAPI contract.

### P2

- Empty-state design for first-time users.
- Last-opened project quick access.

## M1 Structured Import

### P0

- PSD and PSB file import.
- Parse document bounds, layer hierarchy, groups, visibility, opacity, transforms, and names.
- Extract image assets into content-addressed storage.
- Preserve text layers as editable text nodes where practical.
- Create a project scene graph from the imported document.
- Report import warnings without failing the whole import.

### P1

- Preserve layer effects as node metadata when visual fidelity is not supported.
- Import PNG, JPEG, WebP, and SVG as rasterized or vector-backed scene nodes.
- Import job status and structured error messages.
- Cancellation for long-running imports.

### P2

- Figma REST API import behind the same import adapter interface.
- Figma token setup UI.

## M2 Scene Graph and Canvas

### P0

- Retained scene graph as the source of truth.
- CanvasKit rendering for the studio canvas.
- Selection, hover, and deselection.
- Move and resize selected nodes.
- Zoom and pan.
- Layers panel with hierarchy, visibility, lock, and selection.
- Properties panel for position, size, rotation, opacity, and name.
- Undo and redo for canvas and properties operations.
- Autosave of scene changes.

### P1

- Multi-select, group selection, and bounding-box resize.
- Layer reordering by drag or explicit move operations.
- Alignment and distribution helpers.
- Keyboard shortcuts for common operations.
- Delete, duplicate, and paste-in-place.

### P2

- Snap to edges and centers.
- Rulers and simple guides.
- Basic text editing.

## M3 HTML5 Export

### P0

- Export a self-contained HTML5 package from the retained scene graph.
- Preserve scene hierarchy and referenced assets.
- Export PNG, JPEG, WebP, and SVG asset variants.
- Validate the package before marking export complete.
- Preview the exported package in the browser.

### P1

- Export package metadata and an asset manifest.
- Deterministic file names and paths.
- Warning report for unsupported or degraded nodes.

### P2

- Canvas-based export option for complex visual effects.
- Downloadable archive packaging.

## M4 AI Asset Generation

### P0

- Asynchronous AI task lifecycle: created, queued, running, succeeded, failed, cancelled.
- Provider adapter interface for text and image providers.
- Background removal or matting.
- Image upscaling.
- Task status polling and cancellation.
- Retry limits, exponential backoff, and per-user cost controls.

### P1

- AI-generated image placement on the canvas.
- Image editing and outpainting.
- Subject extraction.
- Auto-layering or asset split suggestions.

### P2

- Provider-specific model selection UI.
- Usage and cost reporting.

## M5 Agent REST API

### P0

- Generated OpenAPI contract committed to the repository.
- Versioned REST API under `/api/v1`.
- API keys with scope assignment.
- Rate limiting.
- Task polling endpoints.
- API contract tests.

### P1

- SDK generation from OpenAPI.
- Webhook or event endpoint for task completion.
- Audit log for agent API operations.

## M6 Quality and Ops

### P0

- Visual regression tests for core canvas states.
- API contract tests in CI.
- Security review.
- Performance smoke tests with large PSD/PSB and 4096px assets.
- Structured logs and basic health/readiness endpoints.

### P1

- Usage limits and local credit simulation.
- Deployment runbook.
- Backup and restore documentation.

### P2

- Cloud project sync.
- Real-time collaboration.

## Explicit v1 Non-Goals

- Real-time collaboration.
- Unity, Godot, Cocos Creator, and Unreal exporters.
- Spine, frame animation, sprite atlas, and bitmap font export.
- Cloud subscriptions, billing, and credits.
- Any MCP server, including a REST adapter or an engine-specific server.
- Full Adobe Photoshop effect rendering fidelity.
