from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Project, ProjectRevision, Scene, SceneNode


REVISION_FORMAT_VERSION = 1


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat()


def build_scene_snapshot(db: Session, project: Project) -> dict:
    scenes = list(db.scalars(select(Scene).where(Scene.project_id == project.id).order_by(Scene.created_at)).all())
    scene_snapshots = []
    for scene in scenes:
        nodes = list(
            db.scalars(
                select(SceneNode)
                .where(SceneNode.scene_id == scene.id)
                .order_by(SceneNode.order_index, SceneNode.created_at)
            ).all()
        )
        scene_snapshots.append(
            {
                "id": scene.id,
                "project_id": scene.project_id,
                "root_node_id": scene.root_node_id,
                "width": scene.width,
                "height": scene.height,
                "metadata": dict(scene.metadata_ or {}),
                "nodes": [
                    {
                        "id": node.id,
                        "scene_id": node.scene_id,
                        "parent_id": node.parent_id,
                        "type": node.type,
                        "name": node.name,
                        "visible": node.visible,
                        "locked": node.locked,
                        "opacity": node.opacity,
                        "transform": dict(node.transform or {}),
                        "asset_id": node.asset_id,
                        "text_properties": node.text_properties,
                        "style_properties": node.style_properties,
                        "effect_metadata": node.effect_metadata,
                        "order_index": node.order_index,
                    }
                    for node in nodes
                ],
            }
        )
    return {
        "format_version": REVISION_FORMAT_VERSION,
        "project_id": project.id,
        "project_name": project.name,
        "root_scene_id": project.root_scene_id,
        "scenes": scene_snapshots,
    }


def capture_project_revision(db: Session, project: Project) -> ProjectRevision:
    db.flush()
    latest = db.scalar(
        select(func.max(ProjectRevision.revision_number)).where(ProjectRevision.project_id == project.id)
    )
    revision = ProjectRevision(
        id=str(uuid.uuid4()),
        project_id=project.id,
        revision_number=int(latest or 0) + 1,
        scene_snapshot=build_scene_snapshot(db, project),
    )
    db.add(revision)
    return revision


def restore_project_revision(db: Session, project: Project, revision: ProjectRevision) -> None:
    snapshot = revision.scene_snapshot or {}
    if snapshot.get("format_version") != REVISION_FORMAT_VERSION:
        raise ValueError("unsupported_revision_format")
    if snapshot.get("project_id") != project.id:
        raise ValueError("revision_project_mismatch")

    project.name = str(snapshot.get("project_name") or project.name)
    scenes = snapshot.get("scenes")
    if not isinstance(scenes, list):
        raise ValueError("invalid_revision_snapshot")
    scenes_by_id = {scene.id: scene for scene in db.scalars(select(Scene).where(Scene.project_id == project.id)).all()}
    for scene_data in scenes:
        if not isinstance(scene_data, dict):
            raise ValueError("invalid_revision_snapshot")
        scene = scenes_by_id.get(str(scene_data.get("id")))
        if scene is None:
            raise ValueError("revision_scene_missing")
        scene.width = float(scene_data.get("width", scene.width))
        scene.height = float(scene_data.get("height", scene.height))
        scene.root_node_id = scene_data.get("root_node_id")
        scene.metadata_ = dict(scene_data.get("metadata") or {})
        nodes = scene_data.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("invalid_revision_snapshot")
        db.query(SceneNode).filter(SceneNode.scene_id == scene.id).delete(synchronize_session=False)
        db.flush()
        for node_data in nodes:
            if not isinstance(node_data, dict):
                raise ValueError("invalid_revision_snapshot")
            db.add(
                SceneNode(
                    id=str(node_data["id"]),
                    scene_id=scene.id,
                    parent_id=node_data.get("parent_id"),
                    type=str(node_data.get("type", "layer")),
                    name=str(node_data.get("name", "Layer")),
                    visible=bool(node_data.get("visible", True)),
                    locked=bool(node_data.get("locked", False)),
                    opacity=float(node_data.get("opacity", 1)),
                    transform=dict(node_data.get("transform") or {}),
                    asset_id=node_data.get("asset_id"),
                    text_properties=node_data.get("text_properties"),
                    style_properties=node_data.get("style_properties"),
                    effect_metadata=node_data.get("effect_metadata"),
                    order_index=int(node_data.get("order_index", 0)),
                )
            )
    db.flush()
