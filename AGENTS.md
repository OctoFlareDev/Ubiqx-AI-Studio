# AGENTS.md

This file is the shared project memory for all agents working in this repository. Read it before making product, architecture, or milestone decisions.

## Project

The goal is to build a web application in the same product category as [studio.vberai.com](https://studio.vberai.com).

The working project name is `Ubiqx AI Studio`.

## What VberAI Actually Is

Do not treat VberAI as a generic Figma-style image editor. The central product loop is:

`PSD / Figma design -> AI Studio canvas -> structured engine-ready assets -> Unity / Godot / Cocos Creator`

Key characteristics:

- Imports structured design sources, especially Adobe Photoshop PSD/PSB and Figma.
- Uses an AI canvas to view and edit imported designs.
- Converts designs into engine-ready scenes, UI systems, sprites, animations, fonts, audio, and video.
- Exports to multiple target formats:
  - Game engines: Unity, Godot, Cocos Creator, Unreal UMG.
  - Animation: Spine, frame animation, sprite atlases, bitmap fonts.
  - UI/code: Flutter, React Native, SwiftUI.
  - Raster/vector/interchange: PNG, JPG, SVG, PDF, PSD, WebM with alpha.
- Provides MCP plugins for Unity, Godot 4.x, and Cocos Creator, allowing AI agents such as Claude, Cursor, and Windsurf to manipulate engine projects directly.
- Includes local project autosave, cloud projects, credits/subscriptions, feature gating, and collaboration-oriented UI.

The front-end is a Vue/Vite application and uses CanvasKit for canvas rendering.

### Evidence Sources

Confirmed through public web search:

- [AlternativeTo VberAI profile](https://alternativeto.net/software/vberai/about/)
- [Product Hunt VberAI Studio listing](https://www.producthunt.com/p/vberai-studio-ai-game-ui-tool-with-mcp/vberai-studio-ai-game-ui-tool-with-mcp)
- [Godot MCP asset page](https://www.godotengine.org/asset-library/asset/5305)
- [Cocos MCP server README](https://github.com/DaxianLee/cocos-mcp-server/blob/main/README.EN.md)

Observed by inspecting the public `studio.vberai.com` HTML and JavaScript bundle:

- Vue/Vite application with CanvasKit.
- Auth and OAuth routes.
- Payment/subscription/credits endpoints.
- Project and trash endpoints under `/design/projects`.
- AI delivery, task, and image-generation model endpoints under `/ai`.
- Extensive import/export and engine terminology in the shipped UI strings.

The web sources are sufficient to establish product direction. A feature-by-feature specification still requires access to `vberai.com`, its documentation, or a signed-in instance.

## Original Instruction

The user initially provided this product direction:

1. Focus on core functionality around game art asset generation and processing.
2. Prioritize the project page canvas function, similar to Figma.
3. Local image processing: import, crop, split, and export.
4. AI image processing: generation, editing, outpainting, upscaling, extraction, background removal, and layer splitting.
5. Use a front-end/back-end separation, with the backend exposing an API for agents.

The AI development process was:

1. Prepare baseline documentation: PRD, FEATURE-LIST, TECH-CONSTRAINTS, ACCEPTANCE-CRITERIA, and MILESTONES.
2. Configure Codex skills and MCP tools for design and code review.
3. Set phase-level goals by milestone.
4. Execute each phase with PLAN, PROGRESS, and WORKLOG so sessions can resume context after restarts.
5. Configure self-verification, including unit tests, integration tests, and Playwright browser automation where applicable.
6. Add human checkpoints at milestones.

## Product Thesis After Research

The original instruction is directionally useful, but the feature priority needs correction.

VberAI's defensible value is not generic image editing or a Figma-like canvas alone. It is the structured design-to-game-engine delivery loop.

The project should therefore position itself around:

1. Importing a structured design source, prioritizing PSD/PSB first and Figma second.
2. Parsing that source into a retained scene graph rather than treating it as flat pixels.
3. Making that scene graph visible and editable on an AI-assisted canvas.
4. Generating or placing assets on the canvas.
5. Exporting to a concrete engine target.
6. Exposing the project, asset, scene, and export operations through a normal API and, later, an MCP server.

## Recommended Scope and Milestones

Suggested initial order:

1. `M0 Walking Skeleton`
   - Front-end shell, back-end API, project CRUD, file upload, minimal auth.
   - Establish CI and Playwright smoke testing early.

2. `M1 Structured Import`
   - PSD/PSB parser first.
   - Figma API import second.
   - Parse layers, groups, text, styles, image assets, and layout metadata into a scene graph.
   - This is the highest-risk and highest-value technical capability.

3. `M2 Scene Graph and Canvas`
   - Build the retained scene graph before the canvas.
   - Add CanvasKit-based rendering with selection, move, resize, zoom, layers panel, undo/redo.

4. `M3 HTML5 Export`
   - The v1 export target is plain HTML5. See `PRD.md` for the resolved product decision.
   - Export a runnable static web package that preserves the scene hierarchy and referenced assets.
   - Unity UGUI, Godot, and Cocos Creator are later exporter targets.

5. `M4 AI Asset Generation`
   - Asynchronous task queue with status, cancellation, retry, and cost control.
   - Start with high-value and lower-risk capabilities: upscaling and background removal/matting.
   - Add generation, editing, outpainting, extraction, and auto-layering later.

6. `M5 Agent API and MCP`
   - REST API with OpenAPI.
   - MCP server over project, asset, scene, node, and export operations.
   - API keys, scopes, rate limits, and task polling.

7. `M6 Quality and Ops`
   - Visual regression, API contract tests, security review, performance, credits/limits, and deployment.

The original local image features should be secondary rather than the first milestone:

- Crop, resize, and export.
- Sprite sheet detection and splitting.
- Nine-slice configuration.
- Transparent pixel trimming.
- PNG/WebP/JPEG/SVG export.

## Architecture Principles

Prefer these decisions unless a later agent documents a better reason:

- Separate front end and back end.
- Backend exposes both the web app API and an agent-facing API.
- Model the project as a structured scene graph, not only as image files.
- Keep local and AI processing as separate subsystems.
- Use asynchronous jobs for expensive AI operations.
- Abstract AI providers so models can be swapped without rewriting the UI.
- Treat import/export as adapter layers with format-specific parsers and target-specific exporters.
- Treat the canvas as a view over the scene graph, with the graph as the source of truth.
- Generate OpenAPI from the start so agent clients and SDKs stay in sync.

## Technical Constraints and Risks

- PSD/PSB parsing is nontrivial. Preserve text, layer structure, effects, and asset references as much as practical.
- Figma import depends on the Figma REST API and access tokens.
- Full Figma-grade canvas behavior is expensive. Do not build it before the import-to-export loop is proven.
- AI image quality is subjective. Use fixed test asset sets plus human review in addition to automated tests.
- AI tasks need cost controls, retry limits, cancellation, and per-user quotas.
- Engine export needs compatibility checks because target engines differ in supported node types and properties.
- CanvasKit and large image assets can create memory and performance constraints.
- The local environment has restricted network access by default. `curl` can reach the internet only when explicitly approved outside the sandbox.

## Document Baseline

Use the user's baseline documentation process, extended with the following when work starts:

- `PRD.md`
- `FEATURE-LIST.md`
- `TECH-CONSTRAINTS.md`
- `ACCEPTANCE-CRITERIA.md`
- `MILESTONES.md`
- `ARCHITECTURE.md`
- `DATA-MODEL.md`
- `API-CONTRACT.md`
- `TEST-PLAN.md`
- `SECURITY-AND-OPS.md`

For every milestone, keep `PLAN.md`, `PROGRESS.md`, and `WORKLOG.md` under a milestone directory so a restarted agent can recover context.

## Definition of Done

Each milestone should have concrete acceptance criteria, for example:

- A structured design file imports without losing the primary scene hierarchy.
- A canvas operation round-trips through the scene graph without data loss.
- An engine export opens in the target engine with expected nodes and assets.
- An AI task reports status, supports cancellation, and never retries indefinitely.
- Agent API operations match the generated OpenAPI contract.

## Open Questions

Resolved v1 answers are recorded in `PRD.md`; this list is retained as historical product context.

These should be resolved before finalizing the PRD:

- Is the primary audience game UI designers, game developers, or art outsourcing teams?
- Which structured source is most important for v1: PSD or Figma?
- Which engine is the first export target: Unity, Godot, or Cocos Creator?
- Does v1 require real-time collaboration, or only local projects plus optional cloud sync?
- Which AI provider or providers are approved?
- What image formats, color depths, transparency modes, and maximum resolutions must v1 support?
- Is MCP support required in v1 or can it follow the REST API?
