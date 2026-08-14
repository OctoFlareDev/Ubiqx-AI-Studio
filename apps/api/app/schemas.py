from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class BootstrapResponse(BaseModel):
    user: "ProfileRead"
    api_key: str


class ProfileRead(ORMModel):
    id: str
    display_name: str
    created_at: datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(default="Agent Key", min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class ApiKeyRead(ORMModel):
    id: str
    name: str
    scopes: list[str]
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(BaseModel):
    key: ApiKeyRead
    api_key: str


class ApiKeyList(BaseModel):
    items: list[ApiKeyRead]
    next_cursor: str | None = None


class ProjectCreate(BaseModel):
    name: str = Field(default="Untitled Project", min_length=1, max_length=160)
    width: float = Field(default=1920, ge=1, le=4096)
    height: float = Field(default=1080, ge=1, le=4096)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name_must_not_be_blank")
        return normalized


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    last_autosaved_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name_must_not_be_blank")
        return normalized


class ProjectRead(ORMModel):
    id: str
    name: str
    root_scene_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    version: int
    last_autosaved_at: datetime | None


class ProjectList(BaseModel):
    items: list[ProjectRead]
    next_cursor: str | None = None


class ProjectRevisionRead(ORMModel):
    id: str
    project_id: str
    revision_number: int
    scene_snapshot: dict[str, Any]
    created_at: datetime


class ProjectRevisionList(BaseModel):
    items: list[ProjectRevisionRead]
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
    version: int


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
    transform: Transform = Field(default_factory=Transform)
    opacity: float = Field(default=1, ge=0, le=1)
    asset_id: str | None = None
    text_properties: dict[str, Any] | None = None
    style_properties: dict[str, Any] | None = None
    effect_metadata: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name_must_not_be_blank")
        return normalized


class SceneNodeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    visible: bool | None = None
    locked: bool | None = None
    opacity: float | None = Field(default=None, ge=0, le=1)
    transform: Transform | None = None
    asset_id: str | None = None
    text_properties: dict[str, Any] | None = None
    style_properties: dict[str, Any] | None = None
    effect_metadata: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name_must_not_be_blank")
        return normalized


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
    version: int


class ImportCreate(BaseModel):
    source_asset_id: str
    adapter: Literal["psd", "raster", "svg"] = "psd"


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
    provider: Literal["local"] = "local"
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
    cancel_requested: bool
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
