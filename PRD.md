# Ubiqx AI Studio PRD

Status: Draft for M0
Last updated: 2026-08-13

## Product Summary

Ubiqx AI Studio is a no-code game UI and asset creation tool. A user can import a structured design, see and edit it on a Figma-like canvas, use AI to generate or process assets, and export a runnable HTML5 package without writing code.

## Primary User

The primary users are people who want an easy-to-use game design tool and do not want to write code or become visual designers first.

They need:

- Fast import of an existing PSD/PSB design.
- A familiar visual canvas for selecting, moving, resizing, and organizing elements.
- AI assistance for generation, cleanup, background removal, upscaling, and asset extraction.
- A one-click export that produces something they can open and run.
- No requirement to understand scene graphs, nodes, shaders, or game engine tooling.

## Core Product Loop

1. Import a structured design source, starting with PSD/PSB.
2. Parse the source into a retained scene graph.
3. View and edit the scene graph on a Figma-like CanvasKit canvas.
4. Generate or process assets with AI.
5. Export a plain HTML5 web package.
6. Expose the same operations through a REST API, with MCP support later.

## Product Principles

- Figma-like UX: left asset/layer panel, center canvas, right properties panel, top toolbar, selection, move, resize, zoom, pan, and undo/redo.
- The scene graph is the source of truth; the canvas is a view over it.
- No-code first: every common workflow must be possible visually.
- Structured import is the entry point, not a flat pixel editor.
- Local-first v1: projects are local with autosave; cloud sync and collaboration come later.
- AI work is asynchronous, cancellable, retry-limited, and cost-controlled.
- AI providers are behind an adapter layer.
- Import and export are adapter layers with format-specific parsers and target-specific exporters.

## V1 Scope

In scope:

- Front-end shell and back-end API.
- Project CRUD, file upload, minimal auth, local autosave.
- PSD/PSB import into a structured scene graph.
- CanvasKit canvas with selection, move, resize, zoom, pan, layers panel, and undo/redo.
- Plain HTML5 export package.
- REST API with generated OpenAPI.
- Initial AI asset processing: upscaling and background removal/matting.
- Asset export formats: PNG, JPEG, WebP, and SVG.

Out of scope for v1:

- Real-time collaboration.
- MCP server.
- Unity, Godot, Cocos Creator, and Unreal exporters.
- Spine, frame animation, sprite atlas, and bitmap font export.
- Cloud projects, subscriptions, credits, and billing.
- Kimi and GLM integrations unless their APIs are stable and approved later.

## Resolved Product Decisions

### Audience

The target user is a non-programmer who wants to turn existing designs into game UI or assets without coding or formal design skills.

### UI Model

The UI should look and feel like Figma because it is familiar and easier to use than game-engine editors.

### Structured Source

PSD/PSB is the first import source. Figma API import comes second.

### First Export Target

The v1 export target is plain HTML5. The deliverable is a self-contained web package that opens in a browser without external tooling.

The exact package format will be confirmed in M3, with DOM/CSS/JS as the default because it preserves hierarchy and is easy for non-programmers to inspect and host. Canvas rendering remains an option for complex visual effects.

Unity UGUI, Godot, Cocos Creator, and other engine targets become later adapters rather than v1 requirements.

### Collaboration

There is no real-time collaboration in v1. Local projects plus autosave are sufficient; cloud sync is optional later.

### AI Providers

Text and structured AI providers:

- OpenAI.
- Anthropic.
- DeepSeek through its OpenAI Responses-compatible interface.

Kimi and GLM are optional candidates, not v1 blockers. They should be feature-flagged or added only after API stability is confirmed.

Image providers:

- GPT Image v2.
- Nano Banana.

All providers are hidden behind a common provider interface so models can be swapped without rewriting the UI.

### Image Formats and Processing Limits

Working format:

- sRGB.
- 8 bits per channel.
- RGBA.
- Straight alpha.

Import formats:

- PSD/PSB, prioritized.
- PNG.
- JPEG.
- WebP.
- SVG.

Export formats:

- PNG.
- JPEG.
- WebP.
- SVG.
- Plain HTML5 package.

Maximum processed or exported dimension:

- 4096 pixels on any side.
- Larger inputs are downsampled with a warning.

PSD/PSB preservation:

- Preserve layer hierarchy, groups, visibility, transforms, opacity, text layers, and image assets where practical.
- Preserve layer effects as metadata even when the canvas cannot reproduce them pixel-perfectly.

## API Strategy

A REST API is the HTTP/JSON interface used by the web app and future AI agents or SDKs. Typical operations use `GET`, `POST`, `PATCH`, and `DELETE`, and return structured JSON.

V1 REST API scope:

- Projects.
- Assets.
- Scenes and scene nodes.
- Imports.
- Exports.
- AI task creation, status polling, and cancellation.

The API contract is generated as OpenAPI from the start.

MCP support is deferred until the REST API and scene model are stable.

## Milestones

### M0 Walking Skeleton

- Vue/Vite front-end shell.
- Back-end API.
- Minimal auth.
- Project CRUD.
- File upload.
- CI and Playwright smoke tests.

### M1 Structured Import

- PSD/PSB parser first.
- Figma API import second.
- Parse layers, groups, text, styles, image assets, and layout metadata into a scene graph.

### M2 Scene Graph and Canvas

- Retained scene graph as the source of truth.
- CanvasKit rendering.
- Selection, move, resize, zoom, pan, layers panel, and undo/redo.

### M3 HTML5 Export

- Export a runnable static HTML5 package.
- Preserve the scene hierarchy and referenced assets.
- Define the package format with a small prototype before the full exporter.

### M4 AI Asset Generation

- Asynchronous task queue with status, cancellation, retry, and cost control.
- Start with upscaling and background removal/matting.
- Add generation, editing, outpainting, extraction, and auto-layering later.

### M5 Agent REST API

- Stabilize the REST API.
- Generate and verify OpenAPI.
- Add API keys, scopes, rate limits, and task polling.

### M6 Quality and Ops

- Visual regression.
- API contract tests.
- Security review.
- Performance testing.
- Credits, limits, and deployment readiness.

## Definition of Done

V1 is not done until:

- A PSD/PSB file imports without losing the primary scene hierarchy.
- A canvas operation round-trips through the scene graph without data loss.
- The HTML5 export opens in a browser and renders the expected scene and assets.
- An AI task reports status, supports cancellation, and never retries indefinitely.
- REST API operations match the generated OpenAPI contract.

## Remaining Product Risks

- The exact HTML5 package format needs a short M3 spike.
- Kimi and GLM are not committed until their API access and stability are confirmed.
- PSD/PSB effect fidelity may require accepting metadata-only preservation for complex layer effects.
- CanvasKit memory use must be tested with large 4096px assets.
