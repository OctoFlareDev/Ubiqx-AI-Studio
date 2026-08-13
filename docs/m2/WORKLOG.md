# M2 Scene Graph and Canvas Worklog

## 2026-08-13

- Added `canvaskit-wasm` and a shared CanvasKit singleton.
- Built `SceneCanvas.vue` with CanvasKit rendering, selection, move, resize, zoom, and pan.
- Added scene node update support to the API client and studio store.
- Added undo/redo, visibility, lock, and node property persistence.
- Added a hierarchical layers panel and node properties panel.
- Added backend node property round-trip and CanvasKit drag e2e coverage.
- Diagnosed and fixed CanvasKit binding failures caused by Vue wrapping WASM objects in reactive proxies.
- Ran API tests, typecheck, web build, and Playwright verification.
