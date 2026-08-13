# M3 HTML5 Export Progress

Status: Ready for human checkpoint

## Current State

- Export jobs are persisted and expose queued, running, succeeded, and failed states.
- Non-empty scenes export as a self-contained ZIP package.
- The package preserves the scene hierarchy, node transforms, visibility, opacity, text, and referenced raster assets.
- PNG, JPEG, WebP, and SVG assets are copied into `assets/`.
- `index.html` renders the exported scene without requiring a local server.
- `scene.json` preserves the retained scene data.
- `manifest.json` records package files, referenced assets, and validation.
- Unsupported effects and missing asset references are reported as structured warnings.
- The studio UI can create an export, poll it, preview it, and download it.

## Next

- Human review of package visual parity.
- Future exporter targets remain deferred.
