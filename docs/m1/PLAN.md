# M1 Structured Import Plan

Status: Ready for human checkpoint

## Goal

Prove that PSD/PSB sources can become a retained scene graph without losing the primary layer and group hierarchy.

## Work Items

- [x] Commit the M0 walking skeleton baseline.
- [x] Add `ImportJob` persistence and REST lifecycle.
- [x] Add the `psd-tools` import adapter.
- [x] Parse document bounds, groups, pixel layers, visibility, opacity, transforms, and text metadata.
- [x] Extract layer images into the content-addressed asset store.
- [x] Materialize the imported hierarchy into the project scene graph.
- [x] Add PSD/PSB import tests and generated fixtures.
- [x] Add the front-end "Import as scene" action and job polling.
- [x] Regenerate the OpenAPI contract.
- [x] Run final full verification and record the human checkpoint.

## Verification

- `python3 -m pytest apps/api/tests -q`
- `npm run typecheck`
- `npm run build:web`
- `npx playwright test`

## Checkpoint

Human review of imported PSD/PSB hierarchy and extracted assets.
