# M2 Scene Graph and Canvas Progress

Status: Ready for human checkpoint

## Current State

- The imported scene graph is the source of truth and is rendered by a shared CanvasKit instance.
- The canvas draws hierarchy, transforms, opacity, visibility, images, and text placeholders.
- Nodes can be selected from the canvas or the layers panel and moved or resized with handles.
- Wheel zoom, middle-mouse/space pan, fit view, and zoom controls are wired.
- The layers panel shows hierarchy depth and supports hide, show, lock, and unlock.
- The properties panel edits name, X/Y, width/height, rotation, and opacity.
- Undo/redo stores node snapshots and persists restored state through the API.
- Node edits call the scene node PATCH endpoint and refresh project autosave.
- CanvasKit WASM objects are kept in `shallowRef` so Embind bindings are not wrapped by Vue proxies.

## Next

- Human review of canvas interactions and undo/redo behavior.
- Preview downsampling for very large assets remains deferred.
