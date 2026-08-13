from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db, init_db
from .deps import get_current_user, get_owned_project
from .models import Asset, LocalUser, Project, Scene, SceneNode
from .schemas import (
    AssetRead,
    BootstrapResponse,
    ErrorEnvelope,
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
from .security import create_api_key, get_or_create_local_user
from .storage import AssetStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
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
    if exc.status_code == status.HTTP_400_BAD_REQUEST and isinstance(exc.detail, str):
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ubiqx-api"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}


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


@app.get("/api/v1/projects", response_model=ProjectList)
def list_projects(
    user: LocalUser = Depends(get_current_user),
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
    user: LocalUser = Depends(get_current_user),
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
    user: LocalUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    return get_owned_project(project_id, user, db)


@app.patch("/api/v1/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    user: LocalUser = Depends(get_current_user),
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
    user: LocalUser = Depends(get_current_user),
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
    user: LocalUser = Depends(get_current_user),
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
    user: LocalUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    project = get_owned_project(project_id, user, db)
    project.status = "deleted"
    project.updated_at = _now()
    db.commit()


@app.get("/api/v1/projects/{project_id}/scene", response_model=SceneRead)
def get_project_scene(
    project_id: str,
    user: LocalUser = Depends(get_current_user),
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
    user: LocalUser = Depends(get_current_user),
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
    user: LocalUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SceneNode:
    project = get_owned_project(project_id, user, db)
    scene = db.get(Scene, project.root_scene_id) if project.root_scene_id else None
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scene_not_found")
    parent_id = payload.parent_id or scene.root_node_id
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
    user: LocalUser = Depends(get_current_user),
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
    user: LocalUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SceneNode:
    node = get_scene_node(scene_id, node_id, user, db)
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
    user: LocalUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    node = get_scene_node(scene_id, node_id, user, db)
    db.delete(node)
    db.commit()


@app.post("/api/v1/scenes/{scene_id}/nodes/{node_id}/move", response_model=SceneNodeRead)
def move_scene_node(
    scene_id: str,
    node_id: str,
    payload: SceneNodeMove,
    user: LocalUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SceneNode:
    node = get_scene_node(scene_id, node_id, user, db)
    if payload.parent_id is not None:
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
    user: LocalUser = Depends(get_current_user),
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
    user: LocalUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Asset]:
    get_owned_project(project_id, user, db)
    return list(db.scalars(select(Asset).where(Asset.project_id == project_id).order_by(Asset.created_at.desc())).all())


@app.get("/api/v1/assets/{asset_id}", response_model=AssetRead)
def get_asset(
    asset_id: str,
    user: LocalUser = Depends(get_current_user),
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
    user: LocalUser = Depends(get_current_user),
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
    user: LocalUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    asset = get_asset(asset_id, user, db)
    db.delete(asset)
    db.commit()
