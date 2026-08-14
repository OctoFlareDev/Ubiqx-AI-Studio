# Ubiqx AI Studio Audit

Audit date: 2026-08-14  
Scope: repository implementation, tests, documentation, running API, and live UI at desktop and mobile widths.

## Verdict

The project has a working walking skeleton for the narrow path `create project -> upload PSD -> import simple PSD hierarchy -> select/move a layer -> export a package`. It is not ready to close v1 or its milestone checkpoints.

The most important gaps are scene-graph integrity, the inability to place ordinary or AI-created assets on the canvas, incorrect canvas interaction math for transformed nodes, a blank export preview in the running UI, weak async/error recovery, and incomplete M6 verification. Several documented claims are ahead of the implementation.

Severity used below:

- **P0 / blocker**: violates a v1 acceptance criterion or can corrupt/lose project state.
- **P1 / high**: a required product workflow is missing or unreliable.
- **P2 / medium**: important quality, accessibility, security, or operational gap.
- **P3 / low**: polish, documentation, or maintainability issue.

## Verification performed

- `python3 -m compileall -q apps/api/app apps/api/tests scripts`: passed.
- `python -m pytest apps/api/tests -q`: passed, 40 tests. One Starlette/httpx deprecation warning was emitted.
- `npm run typecheck`: passed.
- `npm run build:web`: passed. Vite warned that `fs` and `path` were externalized from `canvaskit-wasm` for the browser build.
- `npm run test:e2e`: did not run because the local Playwright Chromium executable is missing. This is an environment/setup block, not a failed app assertion. The CI workflow installs Chromium first.
- Live in-app browser checks covered project creation, empty workspace, PSD upload/import, layer selection, asset selection, AI upscaling, HTML5 export/preview, search with no matches, and a 375x667 viewport.
- A direct API probe confirmed invalid scene parents, self-parenting, cross-scene parenting, root deletion, and whitespace node names are currently accepted.
- A direct upload probe confirmed duplicate-upload temp-file leakage, XML-declaration SVG rejection, and incorrect declared image MIME acceptance.

## 1. Release blockers and correctness defects

### SG-01 — Scene graph parent invariants are not enforced — P0

`POST /projects/{id}/scene/nodes` accepts any `parent_id`, including a nonexistent node or a node from another scene. The move endpoint accepts self-parenting, cross-scene parents, and descendant cycles. `SceneNode.parent_id` is a plain string rather than a constrained relationship.

Evidence: `apps/api/app/main.py:438-463`, `apps/api/app/main.py:522-538`, `apps/api/app/models.py:74-94`.

Observed API results: invalid-parent create returned `201`; self-parent move returned `200`; cross-scene move returned `200`.

Impact: the retained scene graph can become orphaned, cyclic, or cross-linked. The canvas and exporter then silently omit nodes or recurse incorrectly. This directly violates the acyclic scene-graph constraint.

### SG-02 — Root nodes can be deleted or mutated — P0

The node update and delete handlers do not protect the scene root. Deleting the root returned `204` in the probe, leaving `Scene.root_node_id` pointing at a deleted row. Root names and transforms are also mutable.

Evidence: `apps/api/app/main.py:485-519`.

Impact: a single API call can make the project scene unusable and invalidate later canvas/import/export operations.

### SG-03 — Whitespace-only node and project names are accepted — P1

Pydantic validates string length before trimming, then the handlers store the trimmed result. A whitespace-only node name returned `200` with `""`; project updates have the same issue.

Evidence: `apps/api/app/schemas.py:56-64`, `apps/api/app/main.py:346-363`, `apps/api/app/main.py:485-507`.

### WF-01 — Uploaded and AI-produced assets cannot be placed on the canvas — P0

The UI can upload an asset and create an AI output asset, but it has no “add to canvas”, drag-to-canvas, or replace-source action. `SceneNodeCreate` does not accept `asset_id`, text properties, or style properties, so the agent/API path cannot create an asset-backed node either.

Evidence: `apps/web/src/views/StudioWorkspace.vue:308-320`, `apps/web/src/stores/studio.ts:217-225`, `apps/api/app/schemas.py:117-130`.

Observed UI behavior: after upscaling, `Button-upscaled.png` appeared only in the asset list, was not selected automatically, and did not appear on the canvas.

Impact: this breaks the central product loop of generating/processing assets and using them in a scene.

### CV-01 — Locked nodes can still be selected and moved from the canvas — P0

The resize path checks `selectedNode.locked`, but the hit-test/move path does not check `hit.locked`. A locked node returned from `hitTest` immediately starts a move mutation.

Evidence: `apps/web/src/components/SceneCanvas.vue:338-375`.

### CV-02 — Selection, hit testing, and fit-to-view do not account for rotation or scale — P0

Rendering applies rotation and scale, while absolute transforms, selection rectangles, hit testing, resize handles, and content bounds use only additive x/y and raw width/height. Parent rotations/scales are also ignored.

Evidence: `apps/web/src/components/SceneCanvas.vue:189-232`, `apps/web/src/components/SceneCanvas.vue:301-335`, `apps/web/src/components/SceneCanvas.vue:494-554`.

Impact: transformed imported layers cannot be reliably selected, moved, resized, framed, or round-tripped. Export uses the same incomplete bounds logic in `apps/api/app/export_service.py:54-103`.

### EX-01 — Export preview is blank in the running UI — P0

After a successful export, the live preview modal opened with a blank light-gray iframe instead of the exported scene. The static preview file contained scene data and renderer code, so the exact iframe/blob/browser cause still needs isolation, but the product behavior is broken.

Evidence: `apps/web/src/stores/studio.ts:201-205`, `apps/web/src/views/StudioWorkspace.vue:503-514`, renderer source `apps/api/app/export_service.py:395-510`.

### EX-02 — Export validation reports success without validating rendered content — P0

The manifest hard-codes `validation.passed: true`; package validation checks that a ZIP and three required files exist, but does not verify hashes, node reachability, asset references, or that the generated HTML renders.

Evidence: `apps/api/app/export_service.py:302-371`.

Impact: an export can be marked successful while nodes are omitted or the preview is blank.

### EX-03 — Every export overwrites the same `latest` package — P1

All jobs write to `exports/{project_id}/latest`, including `html5.zip`, `preview.html`, and the package directory. Older `ExportJob.output_path` values therefore point to mutable output and can download a later export.

Evidence: `apps/api/app/export_service.py:154-158`, `apps/api/app/export_service.py:308-320`.

### JOB-01 — Background jobs are process-local and have no timeout/recovery — P0

Import, export, and AI work are scheduled with FastAPI `BackgroundTasks`. The cancellation sets are in process memory; polling loops have no deadline; there is no worker lease, restart recovery, or reconciliation for rows left in `queued`/`running` after a process restart.

Evidence: `apps/api/app/main.py:641-668`, `apps/api/app/main.py:710-736`, `apps/api/app/main.py:790-817`, `apps/api/app/import_service.py:20-21`, `apps/api/app/ai_service.py:23-27`.

Impact: a task can remain non-terminal forever, and cancellation is not reliable across workers.

### JOB-02 — Front-end polling can wait forever — P1

Import, export, and AI polling use unconditional `while (true)` loops with no timeout, retry policy, or recovery UI. A network failure rejects the promise; a stuck backend leaves the UI waiting indefinitely.

Evidence: `apps/web/src/stores/studio.ts:163-169`, `apps/web/src/stores/studio.ts:193-199`, `apps/web/src/stores/studio.ts:237-243`.

### SAVE-01 — “Saved” state is not tied to actual scene persistence — P1

The workspace initializes `saveState` to `saved` and only changes it for project rename/manual Save. Scene mutations use a separate store flag and call `PATCH project` as a timestamp touch; there is no debounced autosave, immutable revision, recovery point, or save-conflict handling.

Evidence: `apps/web/src/views/StudioWorkspace.vue:33-90`, `apps/web/src/stores/studio.ts:265-337`, `apps/api/app/db.py:24-27`.

The documented `ProjectRevision` model does not exist: `DATA-MODEL.md:236-272` describes it, but `apps/api/app/models.py` ends without one.

## 2. UI and interaction findings

### UI-01 — Empty workspace has no primary import/add-content call to action — P1

An empty project shows a blank checkerboard and “No layers”. The only import route is the top-bar button, which is not represented in the canvas empty state. This is especially problematic on mobile, where that button is hidden.

Evidence: `apps/web/src/views/StudioWorkspace.vue:222-237`, `apps/web/src/views/StudioWorkspace.vue:261-332`.

### UI-02 — Selecting an asset while a layer is selected shows the layer properties — P1

Asset rows update `selectedAssetId` but do not clear `studio.selectedNodeId`. The properties template checks `studio.selectedNode` before `selectedAsset`, so the asset actions are hidden until the user manually deselects the layer.

Evidence: `apps/web/src/views/StudioWorkspace.vue:263-320`, `apps/web/src/views/StudioWorkspace.vue:377-422`.

This was reproduced live after importing `basic.psd`.

### UI-03 — Mobile layout removes core workflows — P1

At 375x667 the sidebar becomes icon-only, the Layers/Assets panel and properties panel disappear, and the Import button is hidden. The remaining canvas has no visible path to upload, inspect assets, or edit properties. The project title also truncates to an unusable fragment.

Evidence: `apps/web/src/styles.css:1030-1082`.

### UI-04 — Mobile navigation icon loses an accessible name — P2

The Projects button has visible text only in the desktop layout; the responsive CSS hides the text and the button has no `aria-label`. The Assets button has a `title`, but should also expose an explicit accessible name.

Evidence: `apps/web/src/components/AppSidebar.vue:26-40`, `apps/web/src/styles.css:1039-1043`.

### UI-05 — “No search matches” is presented as “create your first project” — P1

`filteredProjects.length === 0` always renders `EmptyProjectState`, even when `studio.projects` is non-empty and the search query simply has no matches.

Evidence: `apps/web/src/views/ProjectListView.vue:14-18`, `apps/web/src/views/ProjectListView.vue:88-106`.

This was reproduced with a gibberish search query while a project existed.

### UI-06 — Opacity property layout is clipped — P2

The opacity row has five grid children but `.property-field` defines four columns. In the 260px properties panel, the “Opacity” label is visibly clipped and the range control is squeezed.

Evidence: `apps/web/src/views/StudioWorkspace.vue:404-420`, `apps/web/src/styles.css:868-889`.

### UI-07 — Asset and project previews are missing — P2

Assets are rendered as generic file icons with filename/size only; project cards use a generic folder icon. There are no thumbnails, dimensions, canvas snapshots, or quick visual previews, which is weak for an image/design studio.

Evidence: `apps/web/src/views/StudioWorkspace.vue:308-320`, `apps/web/src/components/ProjectCard.vue:54-72`.

### UI-08 — Asset removal is destructive and mislabeled — P1

The button says “Remove asset reference” but calls `DELETE /assets/{id}`, which deletes the asset database row. It has no confirmation, no dependency check, and can leave scene nodes referencing a missing asset. Content-addressed bytes are also not garbage-collected.

Evidence: `apps/web/src/views/StudioWorkspace.vue:104-108`, `apps/web/src/views/StudioWorkspace.vue:433-435`, `apps/api/app/main.py:620-628`.

### UI-09 — Async UI handlers do not consistently catch errors — P1

Upload, asset import, AI actions, preview, download, rename, archive, and delete handlers are invoked without a shared error boundary. Only a subset of workflows renders `studio.error`; network errors can become unhandled promise rejections or leave stale UI state.

Evidence: `apps/web/src/views/StudioWorkspace.vue:96-150`, `apps/web/src/views/ProjectListView.vue:36-50`, `apps/web/src/stores/studio.ts:131-142`.

### UI-10 — Opening a project can leave a blank workspace after a load failure — P1

`openProject` assigns `currentProjectId` before fetching scene/assets. On failure it stores an error but leaves the route in workspace mode with empty scene state; the workspace does not render a general error/retry state.

Evidence: `apps/web/src/stores/studio.ts:113-129`, `apps/web/src/App.vue:9-23`.

### UI-11 — Preview dialog lacks keyboard focus management — P2

The modal has `role="dialog"` but no focus trap, initial focus, return focus, or Escape-to-close behavior. The global Escape handler deselects a node instead of closing the modal.

Evidence: `apps/web/src/views/StudioWorkspace.vue:503-514`, `apps/web/src/components/SceneCanvas.vue:556-569`.

### UI-12 — Project cards and layer rows are not fully keyboard accessible — P2

Project cards use `tabindex="0"` and handle Enter but not Space and have no button semantics. Layer rows are clickable `div` elements with no focusability or keyboard activation.

Evidence: `apps/web/src/components/ProjectCard.vue:54-85`, `apps/web/src/views/StudioWorkspace.vue:263-270`.

### UI-13 — Global Assets navigation has no project behavior — P2

The sidebar can call `setActivePanel('assets')` while the project list is displayed, but there is no project open and no asset library view. The click appears actionable but has no visible effect.

Evidence: `apps/web/src/components/AppSidebar.vue:10-16`, `apps/web/src/App.vue:17-23`.

### UI-14 — Download filename is inconsistent — P3

The backend derives a safe project-based filename, but the browser client always downloads `ubiqx-html5-export.zip`.

Evidence: `apps/api/app/main.py:760-762`, `apps/web/src/stores/studio.ts:206-215`.

## 3. Canvas and scene-editor omissions

These are required or important in the M2 feature list but are not implemented:

- Multi-select, group selection, and multi-node bounding-box resize.
- Layer reorder by drag or explicit move UI.
- Alignment and distribution.
- Delete, duplicate, and paste-in-place.
- Snap, rulers, guides, and basic text editing.
- Asset drag/drop or placement onto the scene.
- Full text typography rendering/editing; CanvasKit uses the default typeface and draws a single line, while imported metadata is richer.

Evidence: `FEATURE-LIST.md:65-91`, `apps/web/src/components/SceneCanvas.vue:234-249`, `apps/web/src/views/StudioWorkspace.vue:261-421`.

Additional implementation defects:

- Image-load failures are swallowed and remain indistinguishable placeholders; there is no retry or user-visible asset error: `apps/web/src/components/SceneCanvas.vue:126-143`.
- Canvas resizing listens only to `window.resize`, not a `ResizeObserver`, so pane/layout changes can leave the drawing surface at stale dimensions: `apps/web/src/components/SceneCanvas.vue:78-85`, `apps/web/src/components/SceneCanvas.vue:109-124`.
- Zoom toolbar buttons zoom around the scene origin rather than preserving the cursor point, unlike wheel zoom: `apps/web/src/components/SceneCanvas.vue:461-492`.
- CanvasKit initialization failure displays text over an unusable canvas rather than providing a functional degraded fallback, despite the browser-support constraint: `apps/web/src/components/SceneCanvas.vue:97-105`, `apps/web/src/components/SceneCanvas.vue:611-627`, `TECH-CONSTRAINTS.md:102-105`.

## 4. API, persistence, and contract gaps

### API-01 — Scene node creation is too weak for the product model — P1

The scene node API cannot assign assets, text properties, style properties, or effect metadata when creating a node. It only creates a generic node with transform and opacity.

Evidence: `apps/api/app/schemas.py:117-151`, `apps/api/app/main.py:438-463`.

### API-02 — No optimistic concurrency or idempotency — P1

The API has no scene/node version fields, stale-write `409` handling, or `Idempotency-Key` implementation. The contract and technical constraints describe idempotent mutation retries, but source search finds no implementation.

Evidence: `API-CONTRACT.md:214-222`, `TECH-CONSTRAINTS.md:84-91`, `apps/web/src/stores/studio.ts:265-337`.

### API-03 — No generated TypeScript client — P2

The front end contains a hand-written request wrapper and hand-written endpoint types. The technical constraint and feature list require a generated OpenAPI client.

Evidence: `TECH-CONSTRAINTS.md:12-19`, `FEATURE-LIST.md:31-35`, `apps/web/src/services/api.ts:1-184`.

### API-04 — Documented `ProjectRevision` and schema migrations are absent — P1

Database startup uses `Base.metadata.create_all` only. There is no revision model and no migration/version upgrade path.

Evidence: `apps/api/app/db.py:24-27`, `apps/api/app/models.py:74-165`, `DATA-MODEL.md:236-272`.

Impact: schema changes are unsafe, and local autosave cannot recover prior project state.

### API-05 — Archived projects remain directly addressable, but there is no archive/trash UI — P2

Ownership checks reject only `deleted`, while the list returns only `active`. Archived projects can still be fetched by ID, but the web UI offers no archived list or restore/trash view even though restore exists in the API/store.

Evidence: `apps/api/app/deps.py:56-60`, `apps/api/app/main.py:287-297`, `apps/web/src/stores/studio.ts:99-112`.

### API-06 — Error schema is inconsistent and incomplete — P1

`ErrorEnvelope` is defined as flat `code/message/request_id`, while handlers return nested `{ "error": {...} }`. It is not used as a response model, and there is no global exception handler for unexpected 500s. The generated contract therefore does not describe the stable error responses claimed by the API document.

Evidence: `apps/api/app/schemas.py:13-16`, `apps/api/app/main.py:143-169`.

### API-07 — Rate limiting is process-local and omits standard retry metadata — P2

The limiter is an in-memory dictionary with no expired-key cleanup and is not shared across processes. The 429 response has no `Retry-After` header.

Evidence: `apps/api/app/rate_limit.py:11-45`, `apps/api/app/main.py:94-109`.

### API-08 — API documentation promises pagination that handlers do not implement — P2

The contract describes `limit`/`cursor` list queries, but project and AI list handlers accept no pagination parameters and always return `next_cursor: null`.

Evidence: `API-CONTRACT.md:197-212`, `apps/api/app/main.py:287-297`, `apps/api/app/main.py:830-842`.

### API-09 — `ready` can throw instead of reporting degraded state — P2

The database probe is outside the `try` blocks used for storage directories. A database exception can produce an unstructured 500 rather than the documented degraded readiness response.

Evidence: `apps/api/app/main.py:195-214`.

## 5. Upload and import defects

### IMP-01 — Raster/SVG uploads are not importable into the scene — P1

The upload picker accepts PNG/JPEG/WebP/SVG, but import requests only accept adapter `psd`, and the route rejects any source whose media type is not Photoshop.

Evidence: `apps/api/app/schemas.py:157-160`, `apps/api/app/main.py:641-655`.

This contradicts the M1 feature/PRD import format list.

### IMP-02 — SVG detection reads too little data — P1

`_detect_kind` retains only 16 bytes, then tries to find `<svg` within those bytes. A valid SVG with an XML declaration or a longer preamble can be rejected. The documented SVG path was rejected in the direct probe.

Evidence: `apps/api/app/storage.py:23-35`, `apps/api/app/storage.py:75-89`.

### IMP-03 — Declared MIME validation is too permissive — P1

The upload check rejects only non-image declared types. It does not require the declared MIME to match the extension/detected type. An SVG uploaded with `image/png` was accepted and returned as SVG media type in the probe.

Evidence: `apps/api/app/storage.py:91-105`.

### IMP-04 — Duplicate uploads leak temporary files — P1

When the content-addressed destination already exists, `_persist` does not remove the temporary source. A duplicate upload left a file in the temp directory during the probe.

Evidence: `apps/api/app/storage.py:42-47`, `apps/api/app/storage.py:97-105`.

### IMP-05 — Uploads do not record dimensions or image metadata — P2

Uploaded assets are stored with `metadata={}` and no width/height extraction. AI usage consequently reports zero input pixels for ordinary uploads.

Evidence: `apps/api/app/main.py:541-579`, `apps/api/app/models.py:97-113`, `apps/api/app/ai_service.py:251-268`.

### IMP-06 — 4096px policy is applied to derived layer images, not source documents — P1

The parser opens the PSD/PSB and uses the original document dimensions; only individual rasterized layer composites are downsampled. Oversized source documents are not rejected/downsampled with a document-level warning.

Evidence: `apps/api/app/import_service.py:152-174`, `apps/api/app/import_service.py:215-231`, `PRD.md:137-145`.

### IMP-07 — Unsupported PSD layers are silently dropped — P1

Background, adjustment, and brightness/contrast layers return `None` without a warning. This conflicts with the requirement to preserve unsupported effects as metadata or report them.

Evidence: `apps/api/app/import_service.py:176-178`.

### IMP-08 — Effect metadata is not structured — P2

Effects are stored as `repr(effects)`, which is not a stable interchange representation and cannot be reliably consumed by export or agent clients.

Evidence: `apps/api/app/import_service.py:129-143`.

### IMP-09 — Import cleanup and progress are incomplete — P2

Layer assets are written before the scene transaction is committed; a later import failure can leave unreferenced content-addressed files. Progress jumps from 0 to 0.6 to 1 rather than reflecting parser work, and there is no resource/time limit around PSD parsing.

Evidence: `apps/api/app/import_service.py:251-314`, `apps/api/app/import_service.py:215-248`.

## 6. Export fidelity defects

### EXP-01 — Orphaned/invalid nodes can be counted but not rendered — P1

The exporter includes every non-root node in `scene_data`, but the HTML renderer starts only from root children. Invalid parent IDs therefore remain in the manifest/node count while being absent from the visible output.

Evidence: `apps/api/app/export_service.py:138-145`, `apps/api/app/export_service.py:276-293`, `apps/api/app/export_service.py:429-493`.

### EXP-02 — CSS and CanvasKit transform semantics differ — P1

CanvasKit rotates around the local origin; the HTML renderer applies CSS transforms without setting `transform-origin`, so CSS defaults can rotate around the element center. Bounds also ignore rotation/scale.

Evidence: `apps/web/src/components/SceneCanvas.vue:203-208`, `apps/api/app/export_service.py:457-468`.

### EXP-03 — Export title uses source filename, not project name — P2

`project_name_from_data` reads `scene.metadata.source_name`, which is the imported source filename, rather than `project.name`.

Evidence: `apps/api/app/export_service.py:214-225`, `apps/api/app/export_service.py:395-400`, `apps/api/app/export_service.py:523-525`.

### EXP-04 — Export package hash manifest is incomplete — P2

The manifest hashes files before `manifest.json` itself is written, so the manifest does not describe its own hash. Validation checks presence only, not digest correctness.

Evidence: `apps/api/app/export_service.py:295-320`, `apps/api/app/export_service.py:323-371`.

## 7. AI capability and task-control gaps

### AI-01 — “AI” provider currently contains deterministic image algorithms only — P1

The local provider is Lanczos resize and border-color flood-fill matting. No model-backed provider is registered. The provider registry contains only `local`.

Evidence: `apps/api/app/ai_service.py:185-245`.

This may be an intentional M4 prototype, but it does not yet meet the broader AI generation/editing quality expectation and requires explicit product labeling/human quality review.

### AI-02 — The API accepts `provider: openai` but cannot execute it — P1

The schema accepts `local` or `openai`, but the registry has no `openai` provider, so an API caller can create a task that deterministically fails with `provider_unavailable`.

Evidence: `apps/api/app/schemas.py:193-197`, `apps/api/app/ai_service.py:241-245`, `apps/api/app/ai_service.py:331-336`.

### AI-03 — Cost controls, quotas, and concurrency limits are absent — P1

Usage records always set `estimated_cost` to zero. There are no per-user quotas, concurrency caps, budget checks, or provider spend limits.

Evidence: `apps/api/app/ai_service.py:251-268`, `apps/api/app/ai_service.py:314-398`.

### AI-04 — AI cancellation is only cooperative and process-local — P2

Cancellation is checked before/within some operations through an in-memory set. It cannot reliably interrupt a different worker, and the flood-fill operation checks only every 2048 pixels.

Evidence: `apps/api/app/ai_service.py:123-182`, `apps/api/app/ai_service.py:345-383`.

### AI-05 — AI input support excludes SVG and dimensions are often zero — P2

The task runner accepts only PNG/JPEG/WebP and rejects SVG. Uploaded raster dimensions are not populated, so usage metrics are inaccurate.

Evidence: `apps/api/app/ai_service.py:331-332`, `apps/api/app/main.py:565-575`.

### AI-06 — Required generation/editing/outpainting/extraction/layer splitting are absent — P2 / documented deferral

The UI exposes only upscale and background removal. The feature list marks generation placement, editing, outpainting, subject extraction, and auto-layering as later P1 work; they remain unavailable.

Evidence: `FEATURE-LIST.md:114-135`, `apps/web/src/views/StudioWorkspace.vue:436-455`.

## 8. Authentication, security, and operational gaps

### SEC-01 — Unauthenticated bootstrap returns a wildcard API key — P2 for local-only, P0 if exposed

Bootstrap creates/reuses the first local user and returns a `*`-scope key without authentication. This is accepted in the security review for localhost, but there is no runtime guard that prevents a non-local bind.

Evidence: `apps/api/app/main.py:222-226`, `SECURITY-REVIEW.md:37-46`.

### SEC-02 — API key hashing does not match the “salted hash” documentation — P2

The implementation hashes `user_id:raw_key` with plain SHA-256. There is no per-key random salt or password-hash function, despite the security review stating that keys are salted.

Evidence: `apps/api/app/security.py:59-75`, `SECURITY-REVIEW.md:58-64`.

The random high-entropy bearer key reduces practical brute-force risk, but the implementation and security claim are inconsistent.

### SEC-03 — Browser authentication is a persistent localStorage bearer key — P2

The web app stores the API key in `localStorage`; the backend implements bearer-header auth only, not the local session cookie described in the contract.

Evidence: `apps/web/src/services/api.ts:13-17`, `apps/web/src/services/api.ts:96-108`, `apps/api/app/deps.py:20-31`, `API-CONTRACT.md:19-27`.

### SEC-04 — SVG is unsanitized — P2

SVG is accepted, stored, served, and packaged without sanitization. The security review accepts the residual local-file risk, but SVG is listed as a first-class import/export format and there is no sanitizer or explicit safe-rendering policy in the UI.

Evidence: `apps/api/app/storage.py:12-20`, `SECURITY-REVIEW.md:25-35`.

### SEC-05 — No security/secret scan in CI — P1

The test plan and acceptance criteria require security and secret scans, but CI runs API tests, typecheck, build, Playwright installation, and E2E only.

Evidence: `TEST-PLAN.md:105-115`, `ACCEPTANCE-CRITERIA.md:124-131`, `.github/workflows/ci.yml:25-45`.

## 9. Test, CI, and documentation gaps

### TEST-01 — Playwright verification is not reproducible in the current checkout — P1

The local `npm run test:e2e` command failed before test execution because Chromium was not installed. The repository docs state that 4/4 Playwright tests passed twice, but that claim could not be reproduced without downloading the browser binary.

Evidence: `docs/m6/WORKLOG.md:15`, `.github/workflows/ci.yml:40-44`, `playwright.config.ts:1-24`.

The live in-app browser was used for UI inspection instead; it does not substitute for repository E2E in CI.

### TEST-02 — Visual regression is only screenshot-size smoke testing — P1

`visual.spec.ts` asserts screenshot byte length greater than 5000. It does not compare against baselines, and it does not cover empty state, hidden/locked state, export preview, mobile layout, or error states as required by the test plan.

Evidence: `tests/e2e/visual.spec.ts:5-32`, `TEST-PLAN.md:69-79`.

### TEST-03 — Test fixtures do not cover the documented matrix — P1

The repository has only `basic.psd` and `basic.psb`. The generator contains a background, group, and pixel layer; it does not generate the documented text/effect/oversized/malformed/raster/SVG/transparent/low-resolution fixture set.

Evidence: `apps/api/tests/fixtures/generate_fixtures.py:9-37`, `TEST-PLAN.md:81-94`.

### TEST-04 — Front-end workflows and failure states lack automated coverage — P1

There are no front-end unit tests. Existing E2E does not cover asset-selection precedence, AI output placement, blank preview, search no-match state, mobile workflow, locked-node drag prevention, error recovery, or keyboard accessibility.

Evidence: `tests/e2e/canvas-input.spec.ts`, `tests/e2e/projects.spec.ts`, `tests/e2e/scene-canvas.spec.ts`, `tests/e2e/visual.spec.ts`.

### TEST-05 — Browser support is narrower than the stated target — P2

Playwright config runs Chromium only, while the technical constraints list current Chrome, Edge, Firefox, and Safari.

Evidence: `TECH-CONSTRAINTS.md:102-105`, `playwright.config.ts:12-22`.

### TEST-06 — CI does not run the documented quality gates — P1

CI has no lint step, no frontend unit-test step, no API contract generation/diff command, no real visual baseline comparison, and no security/secret scan.

Evidence: `TEST-PLAN.md:105-115`, `.github/workflows/ci.yml:25-45`.

### DOC-01 — Milestone status and checkpoint records are contradictory — P1

All milestone plans remain `Status: In progress`, while progress files say `Ready for human checkpoint`; worklogs do not contain the required human checkpoint results. M6 explicitly says pixel baselines are deferred, yet M6 is described as ready and its worklog claims Playwright passed twice.

Evidence: `docs/m0/PLAN.md:1-28`, `docs/m0/PROGRESS.md:1-19`, `docs/m6/PLAN.md:1-32`, `docs/m6/PROGRESS.md:1-19`, `docs/m6/WORKLOG.md:12-16`.

### DOC-02 — Security review omits current scene-integrity and upload findings — P1

The review records only seven findings, marks upload validation and key storage “verified”, and does not mention the confirmed invalid-parent acceptance, root deletion, MIME mismatch, SVG XML rejection, or temp-file leak.

Evidence: `SECURITY-REVIEW.md:12-87`, findings `SG-01`, `SG-02`, `IMP-02`, `IMP-03`, and `IMP-04` above.

### DOC-03 — Package dependency boundary is fragile — P3

`canvaskit-wasm` is declared at the repository root, while the web workspace imports it without declaring it in `apps/web/package.json`. The current hoisted install builds, but an isolated workspace/package installation can fail.

Evidence: `package.json`, `apps/web/package.json`, `apps/web/src/components/SceneCanvas.vue:1-8`.

## 10. Explicitly deferred scope (not counted as implementation regressions)

The following are absent but explicitly outside or deferred from the current v1 baseline:

- Figma API import and token setup.
- Unity, Godot, Cocos Creator, Unreal, Spine, sprite atlas, bitmap-font, and other engine exporters.
- MCP server.
- Real-time collaboration, cloud projects, subscriptions, billing, and credits.
- Full Photoshop effect rendering fidelity.
- Remote image providers, image generation, editing, outpainting, extraction, and auto-layering.

Evidence: `PRD.md:56-63`, `PRD.md:175-211`, `FEATURE-LIST.md:175-182`.

These become defects if the intended release scope has expanded beyond the documented v1 decisions.

## Recommended closure order

1. Enforce scene-tree invariants and protect the root; add regression tests.
2. Add asset-backed node creation and an explicit place/replace workflow for uploaded and AI assets.
3. Fix transform math and locked-node interaction, then add transformed-node tests.
4. Fix export preview and replace “file exists” validation with content/render validation; use immutable export job directories.
5. Add durable task timeouts/recovery, bounded polling, and complete error/loading states.
6. Finish upload type validation, SVG handling, dimension metadata, source-size limits, and cleanup.
7. Add real visual baselines, complete fixtures, frontend workflow/accessibility tests, and CI security scans.
8. Reconcile milestone docs and record actual human checkpoints before calling M0-M6 complete.
