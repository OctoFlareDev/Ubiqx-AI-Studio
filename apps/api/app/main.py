from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db, init_db
from .deps import get_current_user, get_owned_project, require_scope
from .logging import configure_logging
from .ai_service import CANCELLATION_REQUESTS as AI_CANCELLATION_REQUESTS, run_ai_task
from .export_service import run_export_job, scene_has_exportable_nodes
from .import_service import CANCELLATION_REQUESTS, run_import_job
from .models import AiTask, ApiKey, Asset, ExportJob, ImportJob, LocalUser, Project, Scene, SceneNode
from .rate_limit import SlidingWindowRateLimiter, rate_limit_key
from .schemas import (
    AiTaskCreate,
    AiTaskList,
    AiTaskRead,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyList,
    ApiKeyRead,
    AssetRead,
    BootstrapResponse,
    ErrorEnvelope,
    ExportCreate,
    ExportJobRead,
    ImportCreate,
    ImportJobRead,
    ProfileRead,
    ProjectCreate,
    ProjectList,
    ProjectRead,
    ProjectUpdate,
    SceneNodeCreate,
    SceneNodeMove,
    SceneNodeRead,
    SceneNodeUpdate,
    SceneRead,
)
from .security import (
    UnknownScopeError,
    create_api_key,
    get_or_create_local_user,
    list_api_keys,
    normalize_scopes,
    revoke_api_key,
)
from .storage import AssetStore


request_logger = logging.getLogger("ubiqx.request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.state.rate_limiter = SlidingWindowRateLimiter(
    settings.rate_limit_per_key,
    settings.rate_limit_window_seconds,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/v1"):
        limiter = getattr(request.app.state, "rate_limiter", None)
        if limiter is not None and not limiter.allow(rate_limit_key(request)):
            request_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex}"
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests. Retry after the rate limit window.",
                        "request_id": request_id,
                    }
                },
            )
    return await call_next(request)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    request_logger.info(
        "request",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        },
    )
    return response


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": {"code": "validation_error", "message": "The request body is invalid.", "request_id": _request_id(request)}},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, str) and exc.status_code in {
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_403_FORBIDDEN,
    }:
        code = exc.detail
    else:
        code = {
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            429: "rate_limited",
        }.get(exc.status_code, "http_error")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": str(exc.detail), "request_id": _request_id(request)}},
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _project_read(project: Project) -> ProjectRead:
    return ProjectRead.model_validate(project)


def _asset_read(asset: Asset) -> AssetRead:
    return AssetRead.model_validate(asset)


def _safe_export_filename(name: str) -> str:
    cleaned = "".join(ch for ch in str(name) if ch.isalnum() or ch in ("-", "_", " ", "."))
    cleaned = cleaned.strip().replace(" ", "_") or "ubiqx"
    return cleaned[:120]


def _get_scene_node_for_parent(db: Session, scene_id: str, parent_id: str) -> SceneNode:
    parent = db.get(SceneNode, parent_id)
    if parent is None or parent.scene_id != scene_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_parent")
    return parent


def _validate_scene_parent(
    db: Session,
    scene_id: str,
    parent_id: str | None,
    *,
    node_id: str | None = None,
) -> None:
    if parent_id is None:
        return
    if node_id is not None and parent_id == node_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_parent")

    parent = _get_scene_node_for_parent(db, scene_id, parent_id)
    if node_id is None:
        return

    nodes = {
        node.id: node.parent_id
        for node in db.scalars(select(SceneNode).where(SceneNode.scene_id == scene_id)).all()
    }
    current_id: str | None = parent.id
    visited: set[str] = set()
    while current_id is not None and current_id not in visited:
        if current_id == node_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_parent")
        visited.add(current_id)
        current_id = nodes.get(current_id)


def _ensure_mutable_scene_node(db: Session, scene_id: str, node: SceneNode) -> None:
    scene = db.get(Scene, scene_id)
    if scene is not None and scene.root_node_id == node.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="root_node_immutable")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ubiqx-api"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)) -> JSONResponse:
    db.execute(text("SELECT 1"))
    checks: dict[str, str] = {"database": "ok"}
    for name, path in (
        ("assets", settings.asset_dir),
        ("exports", settings.export_dir),
        ("tmp", settings.tmp_dir),
    ):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            checks[name] = "error"
            continue
        checks[name] = "ok" if os.access(path, os.W_OK) else "error"
    ready_status = "ready" if all(value == "ok" for value in checks.values()) else "degraded"
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready_status == "ready" else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": ready_status, **checks},
    )


@app.get("/api/v1/health")
def api_health() -> dict:
    return {"status": "ok", "service": "ubiqx-api"}


@app.post("/api/v1/auth/bootstrap", response_model=BootstrapResponse)
def bootstrap(db: Session = Depends(get_db)) -> BootstrapResponse:
    user = get_or_create_local_user(db)
    key, raw_key = create_api_key(db, user)
    return BootstrapResponse(user=ProfileRead.model_validate(user), api_key=raw_key)


@app.get("/api/v1/auth/profile", response_model=ProfileRead)
def profile(user: LocalUser = Depends(get_current_user)) -> LocalUser:
    return user


DEFAULT_READ_SCOPES = [
    "projects:read",
    "assets:read",
    "scenes:read",
    "imports:read",
    "exports:read",
    "ai:read",
]


@app.get("/api/v1/api-keys", response_model=ApiKeyList)
def list_user_api_keys(
    user: LocalUser = Depends(require_scope("api_keys:read")),
    db: Session = Depends(get_db),
) -> ApiKeyList:
    keys = list_api_keys(db, user)
    return ApiKeyList(items=[ApiKeyRead.model_validate(key) for key in keys], next_cursor=None)


@app.post("/api/v1/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_user_api_key(
    payload: ApiKeyCreate,
    user: LocalUser = Depends(require_scope("api_keys:write")),
    db: Session = Depends(get_db),
) -> ApiKeyCreated:
    try:
        normalized = normalize_scopes(payload.scopes or DEFAULT_READ_SCOPES)
    except UnknownScopeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown_scope") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    key, raw_key = create_api_key(
        db,
        user,
        name=payload.name,
        scopes=normalized,
        expires_at=payload.expires_at,
    )
    return ApiKeyCreated(key=ApiKeyRead.model_validate(key), api_key=raw_key)


@app.post("/api/v1/api-keys/{key_id}/revoke", response_model=ApiKeyRead)
def revoke_user_api_key(
    key_id: str,
    user: LocalUser = Depends(require_scope("api_keys:write")),
    db: Session = Depends(get_db),
) -> ApiKey:
    key = db.get(ApiKey, key_id)
    if key is None or key.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="api_key_not_found")
    return revoke_api_key(db, key)


@app.get("/api/v1/projects", response_model=ProjectList)
def list_projects(
    user: LocalUser = Depends(require_scope("projects:read")),
    db: Session = Depends(get_db),
) -> ProjectList:
    projects = db.scalars(
        select(Project)
        .where(Project.user_id == user.id, Project.status == "active")
        .order_by(Project.updated_at.desc())
    ).all()
    return ProjectList(items=[_project_read(project) for project in projects], next_cursor=None)


@app.post("/api/v1/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: LocalUser = Depends(require_scope("projects:write")),
    db: Session = Depends(get_db),
) -> Project:
    project_id = str(uuid.uuid4())
    scene_id = str(uuid.uuid4())
    root_node_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        user_id=user.id,
        name=payload.name,
        root_scene_id=scene_id,
        status="active",
    )
    scene = Scene(
        id=scene_id,
        project_id=project_id,
        root_node_id=root_node_id,
        width=payload.width,
        height=payload.height,
    )
    root = SceneNode(
        id=root_node_id,
        scene_id=scene_id,
        parent_id=None,
        type="root",
        name="Root",
        transform={"x": 0, "y": 0, "width": payload.width, "height": payload.height, "rotation": 0, "scale_x": 1, "scale_y": 1},
    )
    db.add_all([project, scene, root])
    db.commit()
    db.refresh(project)
    return project


@app.get("/api/v1/projects/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str,
    user: LocalUser = Depends(require_scope("projects:read")),
    db: Session = Depends(get_db),
) -> Project:
    return get_owned_project(project_id, user, db)


@app.patch("/api/v1/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    user: LocalUser = Depends(require_scope("projects:write")),
    db: Session = Depends(get_db),
) -> Project:
    project = get_owned_project(project_id, user, db)
    if payload.name is not None:
        project.name = payload.name.strip()
    if payload.last_autosaved_at is not None:
        project.last_autosaved_at = payload.last_autosaved_at
    else:
        project.last_autosaved_at = _now()
    project.updated_at = _now()
    db.commit()
    db.refresh(project)
    return project


@app.post("/api/v1/projects/{project_id}/archive", response_model=ProjectRead)
def archive_project(
    project_id: str,
    user: LocalUser = Depends(require_scope("projects:write")),
    db: Session = Depends(get_db),
) -> Project:
    project = get_owned_project(project_id, user, db)
    project.status = "archived"
    project.updated_at = _now()
    db.commit()
    db.refresh(project)
    return project


@app.post("/api/v1/projects/{project_id}/restore", response_model=ProjectRead)
def restore_project(
    project_id: str,
    user: LocalUser = Depends(require_scope("projects:write")),
    db: Session = Depends(get_db),
) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id or project.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project_not_found")
    project.status = "active"
    project.updated_at = _now()
    db.commit()
    db.refresh(project)
    return project


@app.delete("/api/v1/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    user: LocalUser = Depends(require_scope("projects:write")),
    db: Session = Depends(get_db),
) -> None:
    project = get_owned_project(project_id, user, db)
    project.status = "deleted"
    project.updated_at = _now()
    db.commit()


@app.get("/api/v1/projects/{project_id}/scene", response_model=SceneRead)
def get_project_scene(
    project_id: str,
    user: LocalUser = Depends(require_scope("scenes:read")),
    db: Session = Depends(get_db),
) -> Scene:
    project = get_owned_project(project_id, user, db)
    if project.root_scene_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scene_not_found")
    scene = db.get(Scene, project.root_scene_id)
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scene_not_found")
    return scene


@app.get("/api/v1/scenes/{scene_id}/nodes", response_model=list[SceneNodeRead])
def list_scene_nodes(
    scene_id: str,
    user: LocalUser = Depends(require_scope("scenes:read")),
    db: Session = Depends(get_db),
) -> list[SceneNode]:
    scene = db.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scene_not_found")
    project = db.get(Project, scene.project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project_not_found")
    return list(db.scalars(select(SceneNode).where(SceneNode.scene_id == scene_id).order_by(SceneNode.order_index)).all())


@app.post("/api/v1/projects/{project_id}/scene/nodes", response_model=SceneNodeRead, status_code=status.HTTP_201_CREATED)
def create_scene_node(
    project_id: str,
    payload: SceneNodeCreate,
    user: LocalUser = Depends(require_scope("scenes:write")),
    db: Session = Depends(get_db),
) -> SceneNode:
    project = get_owned_project(project_id, user, db)
    scene = db.get(Scene, project.root_scene_id) if project.root_scene_id else None
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scene_not_found")
    parent_id = payload.parent_id or scene.root_node_id
    _validate_scene_parent(db, scene.id, parent_id)
    node = SceneNode(
        id=str(uuid.uuid4()),
        scene_id=scene.id,
        parent_id=parent_id,
        type=payload.type,
        name=payload.name,
        opacity=payload.opacity,
        transform=payload.transform.model_dump(),
        order_index=len(scene.nodes),
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


@app.get("/api/v1/scenes/{scene_id}/nodes/{node_id}", response_model=SceneNodeRead)
def get_scene_node(
    scene_id: str,
    node_id: str,
    user: LocalUser = Depends(require_scope("scenes:read")),
    db: Session = Depends(get_db),
) -> SceneNode:
    node = db.get(SceneNode, node_id)
    if node is None or node.scene_id != scene_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="node_not_found")
    scene = db.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scene_not_found")
    project = db.get(Project, scene.project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project_not_found")
    return node


@app.patch("/api/v1/scenes/{scene_id}/nodes/{node_id}", response_model=SceneNodeRead)
def update_scene_node(
    scene_id: str,
    node_id: str,
    payload: SceneNodeUpdate,
    user: LocalUser = Depends(require_scope("scenes:write")),
    db: Session = Depends(get_db),
) -> SceneNode:
    node = get_scene_node(scene_id, node_id, user, db)
    _ensure_mutable_scene_node(db, scene_id, node)
    if payload.name is not None:
        node.name = payload.name.strip()
    if payload.visible is not None:
        node.visible = payload.visible
    if payload.locked is not None:
        node.locked = payload.locked
    if payload.opacity is not None:
        node.opacity = payload.opacity
    if payload.transform is not None:
        node.transform = payload.transform.model_dump()
    node.updated_at = _now()
    db.commit()
    db.refresh(node)
    return node


@app.delete("/api/v1/scenes/{scene_id}/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scene_node(
    scene_id: str,
    node_id: str,
    user: LocalUser = Depends(require_scope("scenes:write")),
    db: Session = Depends(get_db),
) -> None:
    node = get_scene_node(scene_id, node_id, user, db)
    _ensure_mutable_scene_node(db, scene_id, node)
    db.delete(node)
    db.commit()


@app.post("/api/v1/scenes/{scene_id}/nodes/{node_id}/move", response_model=SceneNodeRead)
def move_scene_node(
    scene_id: str,
    node_id: str,
    payload: SceneNodeMove,
    user: LocalUser = Depends(require_scope("scenes:write")),
    db: Session = Depends(get_db),
) -> SceneNode:
    node = get_scene_node(scene_id, node_id, user, db)
    _ensure_mutable_scene_node(db, scene_id, node)
    if payload.parent_id is not None:
        _validate_scene_parent(db, scene_id, payload.parent_id, node_id=node.id)
        node.parent_id = payload.parent_id
    if payload.order_index is not None:
        node.order_index = payload.order_index
    node.updated_at = _now()
    db.commit()
    db.refresh(node)
    return node


@app.post("/api/v1/projects/{project_id}/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    project_id: str,
    file: UploadFile = File(...),
    user: LocalUser = Depends(require_scope("assets:write")),
    db: Session = Depends(get_db),
) -> Asset:
    project = get_owned_project(project_id, user, db)
    try:
        stored = await AssetStore().save(file)
    except ValueError as exc:
        code = str(exc)
        if code == "file_too_large":
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="upload_too_large") from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code) from exc

    existing = db.scalar(
        select(Asset).where(
            Asset.project_id == project_id,
            Asset.content_hash == stored["content_hash"],
        )
    )
    if existing is not None:
        return existing
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        content_hash=stored["content_hash"],
        media_type=stored["media_type"],
        original_name=stored["original_name"],
        byte_size=stored["byte_size"],
        storage_path=stored["storage_path"],
        source="upload",
        metadata={},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@app.get("/api/v1/projects/{project_id}/assets", response_model=list[AssetRead])
def list_assets(
    project_id: str,
    user: LocalUser = Depends(require_scope("assets:read")),
    db: Session = Depends(get_db),
) -> list[Asset]:
    get_owned_project(project_id, user, db)
    return list(db.scalars(select(Asset).where(Asset.project_id == project_id).order_by(Asset.created_at.desc())).all())


@app.get("/api/v1/assets/{asset_id}", response_model=AssetRead)
def get_asset(
    asset_id: str,
    user: LocalUser = Depends(require_scope("assets:read")),
    db: Session = Depends(get_db),
) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset_not_found")
    project = db.get(Project, asset.project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset_not_found")
    return asset


@app.get("/api/v1/assets/{asset_id}/content")
def download_asset(
    asset_id: str,
    user: LocalUser = Depends(require_scope("assets:read")),
    db: Session = Depends(get_db),
) -> FileResponse:
    asset = get_asset(asset_id, user, db)
    path = Path(asset.storage_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset_content_missing")
    return FileResponse(path, media_type=asset.media_type, filename=asset.original_name)


@app.delete("/api/v1/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: str,
    user: LocalUser = Depends(require_scope("assets:write")),
    db: Session = Depends(get_db),
) -> None:
    asset = get_asset(asset_id, user, db)
    db.delete(asset)
    db.commit()


def _get_owned_import_job(import_id: str, user: LocalUser, db: Session) -> ImportJob:
    job = db.get(ImportJob, import_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="import_job_not_found")
    project = db.get(Project, job.project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="import_job_not_found")
    return job


@app.post("/api/v1/projects/{project_id}/imports", response_model=ImportJobRead, status_code=status.HTTP_201_CREATED)
def create_import_job(
    project_id: str,
    payload: ImportCreate,
    background_tasks: BackgroundTasks,
    user: LocalUser = Depends(require_scope("imports:write")),
    db: Session = Depends(get_db),
) -> ImportJob:
    project = get_owned_project(project_id, user, db)
    source_asset = get_asset(payload.source_asset_id, user, db)
    if source_asset.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset_not_found")
    if source_asset.media_type != "image/vnd.adobe.photoshop":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported_import_source")
    job = ImportJob(
        id=str(uuid.uuid4()),
        project_id=project_id,
        source_asset_id=source_asset.id,
        adapter=payload.adapter,
        status="queued",
        progress=0,
        warnings=[],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_import_job, job.id)
    return job


@app.get("/api/v1/imports/{import_id}", response_model=ImportJobRead)
def get_import_job(
    import_id: str,
    user: LocalUser = Depends(require_scope("imports:read")),
    db: Session = Depends(get_db),
) -> ImportJob:
    return _get_owned_import_job(import_id, user, db)


@app.post("/api/v1/imports/{import_id}/cancel", response_model=ImportJobRead)
def cancel_import_job(
    import_id: str,
    user: LocalUser = Depends(require_scope("imports:write")),
    db: Session = Depends(get_db),
) -> ImportJob:
    job = _get_owned_import_job(import_id, user, db)
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = _now()
        db.commit()
        db.refresh(job)
        return job
    if job.status == "running":
        CANCELLATION_REQUESTS.add(job.id)
        db.commit()
        db.refresh(job)
    return job


def _get_owned_export_job(export_id: str, user: LocalUser, db: Session) -> ExportJob:
    job = db.get(ExportJob, export_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export_job_not_found")
    project = db.get(Project, job.project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export_job_not_found")
    return job


@app.post("/api/v1/projects/{project_id}/exports", response_model=ExportJobRead, status_code=status.HTTP_201_CREATED)
def create_export_job(
    project_id: str,
    payload: ExportCreate,
    background_tasks: BackgroundTasks,
    user: LocalUser = Depends(require_scope("exports:write")),
    db: Session = Depends(get_db),
) -> ExportJob:
    project = get_owned_project(project_id, user, db)
    scene = db.get(Scene, project.root_scene_id) if project.root_scene_id else None
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scene_not_found")
    if not scene_has_exportable_nodes(db, scene):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scene_empty")
    job = ExportJob(
        id=str(uuid.uuid4()),
        project_id=project_id,
        target=payload.target,
        status="queued",
        manifest={},
        warnings=[],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_export_job, job.id)
    return job


@app.get("/api/v1/exports/{export_id}", response_model=ExportJobRead)
def get_export_job(
    export_id: str,
    user: LocalUser = Depends(require_scope("exports:read")),
    db: Session = Depends(get_db),
) -> ExportJob:
    return _get_owned_export_job(export_id, user, db)


@app.get("/api/v1/exports/{export_id}/download")
def download_export(
    export_id: str,
    user: LocalUser = Depends(require_scope("exports:read")),
    db: Session = Depends(get_db),
) -> FileResponse:
    job = _get_owned_export_job(export_id, user, db)
    if job.status != "succeeded" or not job.output_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="export_not_ready")
    package_path = Path(job.output_path)
    if not package_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export_package_missing")
    project = db.get(Project, job.project_id)
    filename = f"{_safe_export_filename(project.name if project else 'ubiqx')}.html5.zip"
    return FileResponse(package_path, media_type="application/zip", filename=filename)


@app.get("/api/v1/exports/{export_id}/preview")
def export_preview(
    export_id: str,
    user: LocalUser = Depends(require_scope("exports:read")),
    db: Session = Depends(get_db),
) -> FileResponse:
    job = _get_owned_export_job(export_id, user, db)
    if job.status != "succeeded" or not job.output_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="export_not_ready")
    preview_path = Path(job.output_path).parent / "preview.html"
    if not preview_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export_preview_missing")
    return FileResponse(preview_path, media_type="text/html", filename="preview.html")


def _get_owned_ai_task(task_id: str, user: LocalUser, db: Session) -> AiTask:
    task = db.get(AiTask, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ai_task_not_found")
    project = db.get(Project, task.project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ai_task_not_found")
    return task


@app.post("/api/v1/projects/{project_id}/ai-tasks", response_model=AiTaskRead, status_code=status.HTTP_201_CREATED)
def create_ai_task(
    project_id: str,
    payload: AiTaskCreate,
    background_tasks: BackgroundTasks,
    user: LocalUser = Depends(require_scope("ai:write")),
    db: Session = Depends(get_db),
) -> AiTask:
    project = get_owned_project(project_id, user, db)
    input_asset = get_asset(payload.input_asset_id, user, db)
    if input_asset.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset_not_found")
    task = AiTask(
        id=str(uuid.uuid4()),
        project_id=project_id,
        provider=payload.provider,
        operation=payload.operation,
        input_asset_id=input_asset.id,
        options=payload.options,
        status="queued",
        progress=0,
        retry_count=0,
        usage={},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    background_tasks.add_task(run_ai_task, task.id)
    return task


@app.get("/api/v1/ai-tasks/{task_id}", response_model=AiTaskRead)
def get_ai_task(
    task_id: str,
    user: LocalUser = Depends(require_scope("ai:read")),
    db: Session = Depends(get_db),
) -> AiTask:
    return _get_owned_ai_task(task_id, user, db)


@app.get("/api/v1/projects/{project_id}/ai-tasks", response_model=AiTaskList)
def list_ai_tasks(
    project_id: str,
    user: LocalUser = Depends(require_scope("ai:read")),
    db: Session = Depends(get_db),
) -> AiTaskList:
    get_owned_project(project_id, user, db)
    tasks = db.scalars(
        select(AiTask)
        .where(AiTask.project_id == project_id)
        .order_by(AiTask.created_at.desc())
    ).all()
    return AiTaskList(items=[AiTaskRead.model_validate(task) for task in tasks], next_cursor=None)


@app.post("/api/v1/ai-tasks/{task_id}/cancel", response_model=AiTaskRead)
def cancel_ai_task(
    task_id: str,
    user: LocalUser = Depends(require_scope("ai:write")),
    db: Session = Depends(get_db),
) -> AiTask:
    task = _get_owned_ai_task(task_id, user, db)
    if task.status == "queued":
        task.status = "cancelled"
        task.finished_at = _now()
        db.commit()
        db.refresh(task)
        return task
    if task.status == "running":
        AI_CANCELLATION_REQUESTS.add(task.id)
        db.commit()
        db.refresh(task)
    return task
