# M3 HTML5 Export Plan

Status: Ready for human checkpoint

## Goal

Prove the v1 no-code delivery loop by producing a runnable HTML5 package from the retained scene graph.

## Work Items

- [x] Commit the M1 structured import baseline.
- [x] Add `ExportJob` persistence and REST lifecycle.
- [x] Add the HTML5 export adapter.
- [x] Copy referenced PNG, JPEG, WebP, and SVG assets into the package.
- [x] Generate `index.html`, `scene.json`, and `manifest.json`.
- [x] Validate package contents before marking the export as succeeded.
- [x] Add warning reporting for unsupported effects and missing assets.
- [x] Add front-end export creation, polling, preview, and download.
- [x] Add export tests and regenerate the OpenAPI contract.
- [x] Run final verification and record the human checkpoint.

## Verification

- `/tmp/ubiqx-venv/bin/python -m pytest apps/api/tests -q`
- `npm run typecheck`
- `npm run build:web`
- `npx playwright test`

## Checkpoint

Human review of the downloaded HTML5 package in a browser.
