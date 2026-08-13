# M1 Structured Import Progress

Status: Ready for human checkpoint

## Current State

- M0 baseline is committed.
- PSD and PSB imports create a scene graph from source layers.
- Pixel layers are rasterized into content-addressed PNG assets.
- Layer groups, visibility, opacity, names, and transforms are preserved.
- Text layers are converted to text nodes with available typography metadata.
- Import jobs expose queued, running, succeeded, failed, and cancelled states.
- Failed imports leave the previous scene intact.
- Front-end import polling and cancellation are wired.

## Next

- Human review of imported PSD/PSB hierarchy and extracted assets.
- Figma API import remains deferred.
