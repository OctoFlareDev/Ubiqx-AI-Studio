# M2 Scene Graph and Canvas Plan

Status: Ready for human checkpoint

## Goal

Prove that the retained scene graph can be viewed and edited through CanvasKit without data loss.

## Work Items

- [x] Commit the M1 structured import baseline.
- [x] Keep the scene graph as the source of truth for canvas state.
- [x] Add a shared CanvasKit singleton and asynchronous initialization.
- [x] Render the scene hierarchy with transforms, opacity, visibility, images, and text.
- [x] Add selection, move, corner resize, zoom, pan, and fit view.
- [x] Add a hierarchical layers panel with visibility and lock toggles.
- [x] Add a properties panel for name, type, transform, rotation, and opacity.
- [x] Add undo/redo state and keyboard shortcuts.
- [x] Persist node edits through the REST API and autosave project updates.
- [x] Add backend node property round-trip coverage.
- [x] Add a CanvasKit interaction e2e spec.
- [x] Run final full verification and record the human checkpoint.

## Verification

- `/tmp/ubiqx-venv/bin/python -m pytest apps/api/tests -q`
- `npm run typecheck`
- `npm run build:web`
- `npx playwright test`

## Checkpoint

Human review of canvas interactions, undo/redo, and reload persistence.
