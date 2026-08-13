# Ubiqx AI Studio API Contract

Status: Baseline for v1
Last updated: 2026-08-13

## Purpose

This file defines the REST API shape used by the web app and future agent clients. The executable OpenAPI document is generated from the FastAPI implementation and committed as the source of truth.

## Conventions

- Base path: `/api/v1`.
- Content type: `application/json`.
- Timestamps: UTC ISO 8601.
- IDs: UUID strings.
- Versioning: URL prefix `/v1`.
- Authentication: bearer API key or local session.

## Authentication

Requests use:

```http
Authorization: Bearer <api-key>
```

The web app may use a local session cookie during browser usage. Both mechanisms resolve to the same local user and scope model.

## Error Envelope

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request body is invalid.",
    "request_id": "req_01H..."
  }
}
```

HTTP status mapping:

- `400`: invalid request or domain rule.
- `401`: missing or invalid credentials.
- `403`: authenticated but not allowed by scope or project ownership.
- `404`: resource not found.
- `409`: conflict or stale mutation.
- `429`: rate limited.
- `500`: unexpected server error.

## Resource Paths

### Projects

- `GET /projects` list projects.
- `POST /projects` create project.
- `GET /projects/{project_id}` get project.
- `PATCH /projects/{project_id}` update project.
- `POST /projects/{project_id}/archive` archive project.
- `POST /projects/{project_id}/restore` restore archived project.
- `DELETE /projects/{project_id}` soft-delete project.

### Assets

- `POST /projects/{project_id}/assets` upload asset.
- `GET /projects/{project_id}/assets` list assets.
- `GET /assets/{asset_id}` get asset metadata.
- `GET /assets/{asset_id}/content` download asset bytes.
- `DELETE /assets/{asset_id}` remove asset reference.

### Scenes

- `GET /projects/{project_id}/scene` get root scene.
- `POST /projects/{project_id}/scene/nodes` create node.
- `GET /scenes/{scene_id}/nodes/{node_id}` get node.
- `PATCH /scenes/{scene_id}/nodes/{node_id}` update node.
- `DELETE /scenes/{scene_id}/nodes/{node_id}` delete node.
- `POST /scenes/{scene_id}/nodes/{node_id}/move` move or reorder node.

### Imports

- `POST /projects/{project_id}/imports` create import job.
- `GET /imports/{import_id}` get import job.
- `POST /imports/{import_id}/cancel` cancel import job.

### Exports

- `POST /projects/{project_id}/exports` create export job.
- `GET /exports/{export_id}` get export job.
- `GET /exports/{export_id}/download` download export package.
- `GET /exports/{export_id}/preview` preview the generated HTML package.

### AI Tasks

- `POST /projects/{project_id}/ai-tasks` create AI task.
- `GET /ai-tasks/{task_id}` get AI task.
- `GET /projects/{project_id}/ai-tasks` list project AI tasks.
- `POST /ai-tasks/{task_id}/cancel` cancel AI task.

### System

- `GET /health` liveness.
- `GET /ready` readiness.
- `GET /openapi.json` generated contract.
- `GET /docs` interactive OpenAPI UI.

## Request Examples

### Create Project

```json
{
  "name": "Main Menu"
}
```

Response:

```json
{
  "id": "proj_01H...",
  "name": "Main Menu",
  "status": "active",
  "root_scene_id": "scene_01H..."
}
```

### Create Import

```json
{
  "source_asset_id": "asset_01H...",
  "adapter": "psd"
}
```

Response:

```json
{
  "id": "imp_01H...",
  "project_id": "proj_01H...",
  "status": "queued"
}
```

### Create AI Task

```json
{
  "operation": "remove_background",
  "provider": "local",
  "input_asset_id": "asset_01H...",
  "options": {
    "tolerance": 32
  }
}
```

### Create Export

```json
{
  "target": "html5"
}
```

Response:

```json
{
  "id": "exp_01H...",
  "project_id": "proj_01H...",
  "target": "html5",
  "status": "queued"
}
```

The export manifest records the package contents, referenced assets, and validation result before the job reaches `succeeded`.

Response:

```json
{
  "id": "task_01H...",
  "project_id": "proj_01H...",
  "status": "queued"
}
```

## Pagination

List endpoints use:

```http
GET /projects?limit=50&cursor=...
```

Response:

```json
{
  "items": [],
  "next_cursor": null
}
```

## Idempotency

Mutations that retry safely may accept:

```http
Idempotency-Key: <client-generated-value>
```

The server returns the original result for a repeated key within the retention window.

## Task Polling

Long-running operations return a resource with a `status` field. Clients poll the `GET` endpoint and stop on a terminal status.

Terminal statuses:

- `succeeded`
- `failed`
- `cancelled`

## API Keys and Scopes

Initial scopes:

- `projects:read`
- `projects:write`
- `assets:read`
- `assets:write`
- `scenes:read`
- `scenes:write`
- `imports:write`
- `exports:write`
- `ai:write`

The API key creation endpoint is administrative and restricted to the local user.

## Contract Governance

- FastAPI generates `openapi.yaml` or `openapi.json`.
- Generated output is committed after every route or schema change.
- Contract tests compare the running app against the committed contract.
- Breaking changes require a `/v2` path or an explicit v1 compatibility decision.

## MCP

MCP is deferred until this REST contract and the scene model are stable. The future MCP server must expose the same project, asset, scene, node, import, export, and AI task operations rather than introduce a second data model.
