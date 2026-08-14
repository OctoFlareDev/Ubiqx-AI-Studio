# M0 Walking Skeleton Plan

Status: Ready for human checkpoint

## Goal

Prove that the front end, back end, local project model, upload, autosave, and tests can run together as a local-first application.

## Work Items

- [x] Read the v1 baseline documents and confirm M0 scope.
- [x] Create the `apps/web` and `apps/api` package boundaries.
- [x] Implement the FastAPI backend with health, auth, projects, upload, assets, scenes, and OpenAPI.
- [x] Implement the Vue/Vite studio shell with project list, empty state, and studio workspace.
- [x] Add backend tests and a Playwright smoke path.
- [x] Install dependencies and verify the complete local workflow.
- [x] Start the development services and record the local URLs.

## Verification

- `make test-api`
- `npm run typecheck`
- `npm run build:web`
- `npm run test:e2e`

## Checkpoint

Human review after the walking skeleton runs end to end.
