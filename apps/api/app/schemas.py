from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class BootstrapResponse(BaseModel):
    user: "ProfileRead"
    api_key: str


class ProfileRead(ORMModel):
    id: str
    display_name: str
    created_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(default="Untitled Project", min_length=1, max_length=160)
    width: float = Field(default=1920, ge=1, le=4096)
    height: float = Field(default=1080, ge=1, le=4096)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    last_autosaved_at: datetime | None = None


class ProjectRead(ORMModel):
    id: str
    name: str
    root_scene_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    last_autosaved_at: datetime | None


class ProjectList(BaseModel):
    items: list[ProjectRead]
    next_cursor: str | None = None


class AssetRead(ORMModel):
    id: str
    project_id: str
    content_hash: str
    media_type: str
    original_name: str
    width: int | None
    height: int | None
    byte_size: int
    source: str
    metadata: dict[str, Any] = Field(validation_alias="metadata_", serialization_alias="metadata")
    created_at: datetime


class SceneRead(ORMModel):
    id: str
    project_id: str
    root_node_id: str | None
    width: float
    height: float
    metadata: dict[str, Any] = Field(validation_alias="metadata_", serialization_alias="metadata")
    created_at: datetime
    updated_at: datetime


class Transform(BaseModel):
    x: float = 0
    y: float = 0
    width: float = 100
    height: float = 100
    rotation: float = 0
    scale_x: float = 1
    scale_y: float = 1


class SceneNodeCreate(BaseModel):
    parent_id: str | None = None
    type: Literal["group", "layer", "text", "image", "shape"] = "layer"
    name: str = Field(default="Layer", min_length=1, max_length=160)
    transform: Transform = Transform()
    opacity: float = Field(default=1, ge=0, le=1)


class SceneNodeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    visible: bool | None = None
    locked: bool | None = None
    opacity: float | None = Field(default=None, ge=0, le=1)
    transform: Transform | None = None


class SceneNodeMove(BaseModel):
    parent_id: str | None = None
    order_index: int | None = None


class SceneNodeRead(ORMModel):
    id: str
    scene_id: str
    parent_id: str | None
    type: str
    name: str
    visible: bool
    locked: bool
    opacity: float
    transform: dict[str, Any]
    asset_id: str | None
    text_properties: dict[str, Any] | None
    style_properties: dict[str, Any] | None
    effect_metadata: dict[str, Any] | None
    order_index: int
    created_at: datetime
    updated_at: datetime


class ImportCreate(BaseModel):
    source_asset_id: str
    adapter: Literal["psd"] = "psd"


class ImportJobRead(ORMModel):
    id: str
    project_id: str
    source_asset_id: str
    adapter: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    progress: float
    warnings: list[dict[str, Any]]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ExportCreate(BaseModel):
    target: Literal["html5"] = "html5"


class ExportJobRead(ORMModel):
    id: str
    project_id: str
    target: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    manifest: dict[str, Any]
    warnings: list[dict[str, Any]]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AiTaskCreate(BaseModel):
    operation: Literal["upscale", "remove_background"]
    provider: Literal["local", "openai"] = "local"
    input_asset_id: str
    options: dict[str, Any] = Field(default_factory=dict)


class AiTaskRead(ORMModel):
    id: str
    project_id: str
    provider: str
    operation: str
    input_asset_id: str
    output_asset_id: str | None
    options: dict[str, Any]
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    progress: float
    retry_count: int
    last_error: str | None
    usage: dict[str, Any]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AiTaskList(BaseModel):
    items: list[AiTaskRead]
    next_cursor: str | None = None


BootstrapResponse.model_rebuild()
