# M4 AI Asset Generation Progress

Status: Ready for human checkpoint

## Current State

- AI tasks are persisted and expose queued, running, succeeded, failed, and cancelled states.
- The local image provider implements Lanczos upscaling and border flood-fill background removal.
- Provider access is behind an adapter registry, keeping provider-specific code out of the UI.
- Tasks enforce a maximum of three attempts with exponential backoff.
- Cancelled tasks are never retried.
- Usage records include normalized attempt, pixel, and cost metadata.
- The studio can upscale and remove backgrounds from raster assets.

## Next

- Human review of processed image quality.
- Remote image providers remain deferred behind the existing adapter boundary.
