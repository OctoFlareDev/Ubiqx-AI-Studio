from __future__ import annotations

import io
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from psd_tools import PSDImage
from psd_tools.api.layers import Layer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Asset, ImportJob, Project, Scene, SceneNode
from .ops import job_timed_out
from .storage import AssetStore


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
CANCELLATION_REQUESTS: set[str] = set()

logger = logging.getLogger("ubiqx.import")


class ImportFailure(Exception):
    """Raised when a source file cannot be converted into a valid scene."""


@dataclass
class ParsedAsset:
    content_hash: str
    media_type: str
    original_name: str
    byte_size: int
    storage_path: str
    width: int
    height: int


@dataclass
class ParsedNode:
    type: str
    name: str
    visible: bool
    locked: bool
    opacity: float
    transform: dict
    asset: ParsedAsset | None = None
    text_properties: dict | None = None
    style_properties: dict | None = None
    effect_metadata: dict | None = None
    children: list[ParsedNode] = field(default_factory=list)


@dataclass
class ParsedDocument:
    width: float
    height: float
    root: ParsedNode
    warnings: list[dict] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _warning(code: str, message: str, layer: str | None = None) -> dict:
    item = {"code": code, "message": message}
    if layer is not None:
        item["layer"] = layer
    return item


def _transform_for(layer: Layer) -> dict:
    left = float(layer.left or 0)
    top = float(layer.top or 0)
    width = float(layer.width or 0)
    height = float(layer.height or 0)
    return {
        "x": left,
        "y": top,
        "width": width,
        "height": height,
        "rotation": 0,
        "scale_x": 1,
        "scale_y": 1,
    }


def _layer_type(layer: Layer) -> str:
    if layer.is_group():
        return "group"
    if getattr(layer, "kind", None) == "type":
        return "text"
    if getattr(layer, "kind", None) in {"shape", "solidcolor", "gradient", "pattern"}:
        return "shape"
    return "image"


def _text_properties(layer: Layer) -> dict | None:
    if getattr(layer, "kind", None) != "type":
        return None
    result: dict = {
        "text": getattr(layer, "text", ""),
    }
    try:
        typesetting = layer.typesetting
        result["text"] = typesetting.text or result["text"]
        result["writing_direction"] = str(typesetting.writing_direction) if typesetting.writing_direction else None
        if typesetting.fonts:
            result["font_name"] = typesetting.fonts[0].name if typesetting.fonts[0] else None
        if typesetting.runs:
            first = typesetting.runs[0]
            style = first.style
            result["font_size"] = style.font_size
            result["fill_color"] = style.fill_color
            result["faux_bold"] = style.faux_bold
            result["faux_italic"] = style.faux_italic
        if typesetting.paragraphs:
            result["alignment"] = str(typesetting.paragraphs[0].style.justification)
    except Exception:
        # The normalized text block should still survive even when the parser's
        # optional type-setting helpers differ across PSD fixture versions.
        pass
    return result


def _effect_metadata(layer: Layer, warnings: list[dict]) -> dict | None:
    effects = getattr(layer, "effects", None)
    if not effects:
        return None
    warnings.append(
        _warning(
            "unsupported_layer_effects",
            "Layer effects are preserved as metadata and may not render pixel-perfectly.",
            getattr(layer, "name", None),
        )
    )
    return {
        "effects": repr(effects),
        "blend_mode": str(getattr(layer, "blend_mode", "")),
    }


class PSDImportParser:
    def __init__(self, asset_store: AssetStore | None = None, source_name: str = "design") -> None:
        self.asset_store = asset_store or AssetStore()
        self.source_name = source_name
        self.warnings: list[dict] = []

    def parse(self, path: Path | str) -> ParsedDocument:
        source_path = Path(path)
        if not source_path.exists():
            raise ImportFailure("source_file_missing")
        try:
            psd = PSDImage.open(source_path)
        except Exception as exc:
            raise ImportFailure("invalid_psd_file") from exc

        root = ParsedNode(
            type="root",
            name="Root",
            visible=True,
            locked=False,
            opacity=1,
            transform={"x": 0, "y": 0, "width": float(psd.width), "height": float(psd.height), "rotation": 0, "scale_x": 1, "scale_y": 1},
        )
        for order_index, layer in enumerate(psd):
            child = self._convert_layer(layer)
            if child is not None:
                root.children.append(child)

        return ParsedDocument(width=float(psd.width), height=float(psd.height), root=root, warnings=self.warnings)

    def _convert_layer(self, layer: Layer) -> ParsedNode | None:
        if layer.kind in {"background", "adjustment", "brightnesscontrast"}:
            return None
        node_type = _layer_type(layer)
        node = ParsedNode(
            type=node_type,
            name=getattr(layer, "name", "Layer"),
            visible=bool(getattr(layer, "visible", True)),
            locked=bool(getattr(layer, "locked", False)),
            opacity=float(getattr(layer, "opacity", 255) or 255) / 255,
            transform=_transform_for(layer),
            effect_metadata=_effect_metadata(layer, self.warnings),
        )
        if node_type == "group":
            for child in layer:
                converted = self._convert_layer(child)
                if converted is not None:
                    node.children.append(converted)
            return node

        if node_type == "text":
            node.text_properties = _text_properties(layer)
            node.style_properties = {"kind": str(layer.kind)}
            return node

        if node_type in {"image", "shape"}:
            node.asset = self._layer_asset(layer)
            if node.asset is None and node_type == "image":
                self.warnings.append(
                    _warning(
                        "layer_asset_unavailable",
                        "The layer could not be rasterized and was kept as a scene node without image data.",
                        node.name,
                    )
                )
            return node

        return node

    def _layer_asset(self, layer: Layer) -> ParsedAsset | None:
        try:
            image = layer.composite()
        except Exception:
            return None
        if image is None:
            return None
        image = image.convert("RGBA")
        if max(image.size) > 4096:
            ratio = 4096 / max(image.size)
            image = image.resize((max(1, int(image.width * ratio)), max(1, int(image.height * ratio))))
            self.warnings.append(
                _warning(
                    "layer_downsampled",
                    "Layer preview was downsampled to the 4096 pixel processing limit.",
                    getattr(layer, "name", None),
                )
            )
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        stored = self.asset_store.save_bytes(
            buffer.getvalue(),
            original_name=f"{self.source_name} / {getattr(layer, 'name', 'layer')}.png",
            media_type="image/png",
        )
        return ParsedAsset(
            content_hash=stored["content_hash"],
            media_type=stored["media_type"],
            original_name=stored["original_name"],
            byte_size=stored["byte_size"],
            storage_path=stored["storage_path"],
            width=image.width,
            height=image.height,
        )


def run_import_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(ImportJob, job_id)
        if job is None or job.status in TERMINAL_STATUSES:
            return
        logger.info("import_job_started", extra={"job_id": job_id})
        if job_id in CANCELLATION_REQUESTS:
            job.status = "cancelled"
            job.finished_at = _now()
            db.commit()
            return

        job.status = "running"
        job.started_at = _now()
        db.commit()

        if job_timed_out(job.started_at, job.created_at):
            raise ImportFailure("job_timeout")

        source_asset = db.get(Asset, job.source_asset_id)
        if source_asset is None:
            raise ImportFailure("source_asset_missing")
        project = db.get(Project, job.project_id)
        if project is None:
            raise ImportFailure("project_missing")

        if job.adapter == "psd":
            parser = PSDImportParser(source_name=Path(source_asset.original_name).stem)
            parsed = parser.parse(Path(source_asset.storage_path))
        else:
            parsed = _raster_document(source_asset)
        if job_timed_out(job.started_at, job.created_at):
            raise ImportFailure("job_timeout")
        job.progress = 0.6
        job.warnings = parsed.warnings
        db.commit()

        if job_id in CANCELLATION_REQUESTS:
            job.status = "cancelled"
            job.finished_at = _now()
            db.commit()
            return

        if job_timed_out(job.started_at, job.created_at):
            raise ImportFailure("job_timeout")

        _materialize_document(db, project, source_asset, parsed)
        job.progress = 1
        job.status = "succeeded"
        job.finished_at = _now()
        project.last_autosaved_at = _now()
        project.updated_at = _now()
        db.commit()
        logger.info("import_job_succeeded", extra={"job_id": job_id})
    except ImportFailure as exc:
        db.rollback()
        _mark_failed(db, job_id, str(exc))
    except Exception as exc:
        db.rollback()
        _mark_failed(db, job_id, f"import_failed: {type(exc).__name__}")
    finally:
        CANCELLATION_REQUESTS.discard(job_id)
        db.close()


def _mark_failed(db: Session, job_id: str, error: str) -> None:
    job = db.get(ImportJob, job_id)
    if job is None:
        return
    job.status = "failed"
    job.error = error
    job.finished_at = _now()
    logger.info("import_job_failed", extra={"job_id": job_id, "error": error})
    db.commit()


def _materialize_document(
    db: Session,
    project: Project,
    source_asset: Asset,
    parsed: ParsedDocument,
) -> None:
    scene = db.get(Scene, project.root_scene_id) if project.root_scene_id else None
    if scene is None:
        raise ImportFailure("scene_missing")

    scene.width = parsed.width
    scene.height = parsed.height
    scene.metadata_ = {
        "import_adapter": "psd",
        "source_asset_id": source_asset.id,
        "source_name": source_asset.original_name,
    }

    root_node_id = scene.root_node_id
    if root_node_id is None:
        raise ImportFailure("root_node_missing")
    db.query(SceneNode).filter(SceneNode.scene_id == scene.id, SceneNode.id != root_node_id).delete(synchronize_session=False)

    asset_cache: dict[str, Asset] = {}
    order_index = 0
    for child in parsed.root.children:
        order_index = _persist_node_tree(
            db=db,
            scene_id=scene.id,
            parent_id=root_node_id,
            parsed=child,
            project_id=project.id,
            asset_cache=asset_cache,
            order_index=order_index,
        )


def _raster_document(source_asset: Asset) -> ParsedDocument:
    width = float(source_asset.width or 512)
    height = float(source_asset.height or 512)
    node = ParsedNode(
        type="image",
        name=Path(source_asset.original_name).stem or "Image",
        visible=True,
        locked=False,
        opacity=1,
        transform={
            "x": 0,
            "y": 0,
            "width": width,
            "height": height,
            "rotation": 0,
            "scale_x": 1,
            "scale_y": 1,
        },
    )
    node.asset = ParsedAsset(
        content_hash=source_asset.content_hash,
        media_type=source_asset.media_type,
        original_name=source_asset.original_name,
        byte_size=source_asset.byte_size,
        storage_path=source_asset.storage_path,
        width=round(width),
        height=round(height),
    )
    root = ParsedNode(
        type="root",
        name="Root",
        visible=True,
        locked=False,
        opacity=1,
        transform={"x": 0, "y": 0, "width": width, "height": height, "rotation": 0, "scale_x": 1, "scale_y": 1},
        children=[node],
    )
    return ParsedDocument(width=width, height=height, root=root)


def _persist_node_tree(
    db: Session,
    scene_id: str,
    parent_id: str,
    parsed: ParsedNode,
    project_id: str,
    asset_cache: dict[str, Asset],
    order_index: int,
) -> int:
    asset_id = None
    if parsed.asset is not None:
        asset_id = _get_or_create_imported_asset(db, project_id, parsed.asset, asset_cache).id
    node = SceneNode(
        id=str(uuid.uuid4()),
        scene_id=scene_id,
        parent_id=parent_id,
        type=parsed.type,
        name=parsed.name,
        visible=parsed.visible,
        locked=parsed.locked,
        opacity=parsed.opacity,
        transform=parsed.transform,
        asset_id=asset_id,
        text_properties=parsed.text_properties,
        style_properties=parsed.style_properties,
        effect_metadata=parsed.effect_metadata,
        order_index=order_index,
    )
    db.add(node)
    db.flush()
    child_index = order_index + 1
    for child in parsed.children:
        child_index = _persist_node_tree(
            db=db,
            scene_id=scene_id,
            parent_id=node.id,
            parsed=child,
            project_id=project_id,
            asset_cache=asset_cache,
            order_index=child_index,
        )
    return child_index


def _get_or_create_imported_asset(
    db: Session,
    project_id: str,
    parsed: ParsedAsset,
    asset_cache: dict[str, Asset],
) -> Asset:
    cached = asset_cache.get(parsed.content_hash)
    if cached is not None:
        return cached
    existing = db.scalar(
        select(Asset).where(
            Asset.project_id == project_id,
            Asset.content_hash == parsed.content_hash,
        )
    )
    if existing is not None:
        asset_cache[parsed.content_hash] = existing
        return existing
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        content_hash=parsed.content_hash,
        media_type=parsed.media_type,
        original_name=parsed.original_name,
        width=parsed.width,
        height=parsed.height,
        byte_size=parsed.byte_size,
        storage_path=parsed.storage_path,
        source="psd_import",
        metadata={"source": "psd_layer"},
    )
    db.add(asset)
    db.flush()
    asset_cache[parsed.content_hash] = asset
    return asset
