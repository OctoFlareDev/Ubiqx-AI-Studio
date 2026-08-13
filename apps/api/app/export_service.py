from __future__ import annotations

import base64
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .models import Asset, ExportJob, Project, Scene, SceneNode


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}

MEDIA_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


class ExportFailure(Exception):
    """Raised when a scene cannot be converted into a valid HTML5 package."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _warning(code: str, message: str, node: str | None = None) -> dict:
    item = {"code": code, "message": message}
    if node is not None:
        item["node"] = node
    return item


def _extension_for(media_type: str) -> str | None:
    return MEDIA_EXTENSIONS.get(media_type)


def scene_has_exportable_nodes(db: Session, scene: Scene) -> bool:
    if scene is None:
        return False
    node_id = db.scalar(
        select(SceneNode.id)
        .where(SceneNode.scene_id == scene.id, SceneNode.type != "root")
        .limit(1)
    )
    return node_id is not None


def _json_payload(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), default=str)


def _script_safe_json(value: object) -> str:
    return _json_payload(value).replace("</", "<\\/")


def _data_uri(path: Path, media_type: str) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


class HTML5ExportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def export(self, project: Project, scene: Scene) -> tuple[Path, Path, dict, list[dict]]:
        if scene is None:
            raise ExportFailure("scene_missing")

        nodes = list(
            self.db.scalars(
                select(SceneNode)
                .where(SceneNode.scene_id == scene.id)
                .order_by(SceneNode.order_index, SceneNode.created_at)
            ).all()
        )
        exportable_nodes = [node for node in nodes if node.type != "root"]
        if not exportable_nodes:
            raise ExportFailure("scene_empty")

        warnings: list[dict] = []
        asset_ids = {node.asset_id for node in exportable_nodes if node.asset_id}
        assets = list(self.db.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all()) if asset_ids else []
        assets_by_id = {asset.id: asset for asset in assets}

        export_dir = settings.export_dir / project.id / "latest"
        package_dir = export_dir / "package"
        assets_dir = package_dir / "assets"
        package_dir.mkdir(parents=True, exist_ok=True)
        assets_dir.mkdir(parents=True, exist_ok=True)

        asset_files: dict[str, str] = {}
        referenced_assets: list[dict] = []
        for asset in assets:
            extension = _extension_for(asset.media_type)
            if extension is None:
                warnings.append(
                    _warning(
                        "unsupported_asset_type",
                        f"Asset {asset.original_name} uses an unsupported media type and was omitted from the package.",
                        asset.original_name,
                    )
                )
                continue
            source_path = Path(asset.storage_path)
            if not source_path.exists():
                warnings.append(
                    _warning(
                        "asset_content_missing",
                        f"Asset {asset.original_name} could not be found in local storage.",
                        asset.original_name,
                    )
                )
                continue
            relative_path = f"assets/{asset.content_hash[:16]}{extension}"
            destination = package_dir / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copyfile(source_path, destination)
            asset_files[asset.id] = relative_path
            referenced_assets.append(
                {
                    "asset_id": asset.id,
                    "file": relative_path,
                    "media_type": asset.media_type,
                    "original_name": asset.original_name,
                    "width": asset.width,
                    "height": asset.height,
                    "byte_size": asset.byte_size,
                }
            )

        scene_data = {
            "version": 1,
            "target": "html5",
            "scene": {
                "id": scene.id,
                "width": scene.width,
                "height": scene.height,
                "metadata": scene.metadata_,
            },
            "root_node_id": scene.root_node_id,
            "nodes": [],
        }

        for node in exportable_nodes:
            asset_file = None
            if node.asset_id:
                asset = assets_by_id.get(node.asset_id)
                if asset is None:
                    warnings.append(
                        _warning(
                            "missing_asset_reference",
                            "The node references an asset that does not exist in this project.",
                            node.name,
                        )
                    )
                else:
                    asset_file = asset_files.get(asset.id)
                    if asset_file is None and node.type in {"image", "shape"}:
                        warnings.append(
                            _warning(
                                "asset_omitted",
                                "The node asset could not be included in the export package.",
                                node.name,
                            )
                        )
            elif node.type in {"image", "shape"}:
                warnings.append(
                    _warning(
                        "missing_raster_asset",
                        "A raster node does not reference a stored asset.",
                        node.name,
                    )
                )

            if node.effect_metadata:
                warnings.append(
                    _warning(
                        "unsupported_visual_effect",
                        "Layer effects are preserved as metadata and may not render pixel-perfectly in HTML5.",
                        node.name,
                    )
                )

            scene_data["nodes"].append(
                {
                    "id": node.id,
                    "parent_id": node.parent_id,
                    "type": node.type,
                    "name": node.name,
                    "visible": node.visible,
                    "locked": node.locked,
                    "opacity": node.opacity,
                    "transform": node.transform or {},
                    "asset_id": node.asset_id,
                    "asset_file": asset_file,
                    "text_properties": node.text_properties,
                    "style_properties": node.style_properties,
                    "effect_metadata": node.effect_metadata,
                    "order_index": node.order_index,
                }
            )

        scene_payload = _json_payload(scene_data)
        (package_dir / "scene.json").write_text(scene_payload, encoding="utf-8")
        (package_dir / "index.html").write_text(
            self._render_html(scene_data, embedded_assets=False),
            encoding="utf-8",
        )

        manifest = self._build_manifest(package_dir, scene_data, referenced_assets, warnings)
        (package_dir / "manifest.json").write_text(
            _json_payload(manifest),
            encoding="utf-8",
        )

        preview_path = export_dir / "preview.html"
        preview_path.write_text(
            self._render_html(scene_data, embedded_assets=True, assets_by_id=assets_by_id),
            encoding="utf-8",
        )

        package_path = export_dir / "html5.zip"
        with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(package_dir.rglob("*")):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(package_dir).as_posix())

        self._validate_package(package_path, manifest)
        return package_path, export_dir, manifest, warnings

    def _build_manifest(
        self,
        package_dir: Path,
        scene_data: dict,
        referenced_assets: list[dict],
        warnings: list[dict],
    ) -> dict:
        files: dict[str, dict] = {}
        for file_path in sorted(package_dir.rglob("*")):
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(package_dir).as_posix()
            digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            files[relative] = {
                "sha256": digest,
                "byte_size": file_path.stat().st_size,
            }

        node_count = len(scene_data["nodes"])
        asset_count = len(referenced_assets)
        return {
            "format_version": 1,
            "target": "html5",
            "scene": scene_data["scene"],
            "files": files,
            "referenced_assets": referenced_assets,
            "validation": {
                "passed": True,
                "node_count": node_count,
                "asset_count": asset_count,
                "warning_count": len(warnings),
            },
        }

    def _validate_package(self, package_path: Path, manifest: dict) -> None:
        if not package_path.exists() or package_path.stat().st_size == 0:
            raise ExportFailure("export_package_missing")
        try:
            with zipfile.ZipFile(package_path) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile as exc:
            raise ExportFailure("export_package_invalid") from exc

        for required in ("index.html", "scene.json", "manifest.json"):
            if required not in names:
                raise ExportFailure("export_validation_failed")
        for relative in manifest["files"]:
            if relative not in names:
                raise ExportFailure("export_validation_failed")

    def _render_html(
        self,
        scene_data: dict,
        *,
        embedded_assets: bool,
        assets_by_id: dict[str, Asset] | None = None,
    ) -> str:
        render_data = json.loads(_json_payload(scene_data))
        if embedded_assets:
            for node in render_data["nodes"]:
                asset_file = node.get("asset_file")
                asset_id = node.get("asset_id")
                if not asset_file or not asset_id:
                    continue
                asset = (assets_by_id or {}).get(asset_id)
                if asset is None:
                    continue
                source_path = Path(asset.storage_path)
                if not source_path.exists():
                    continue
                node["asset_file"] = _data_uri(source_path, asset.media_type)

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{self._escape_html(project_name_from_data(scene_data))}</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    * {{ box-sizing: border-box; }}
    html, body {{ min-height: 100%; margin: 0; background: #eef1f4; color: #17202a; }}
    body {{ display: grid; place-items: start center; padding: 24px; overflow: auto; }}
    .viewport {{ position: relative; overflow: hidden; box-shadow: 0 14px 36px rgb(38 52 67 / 18%); }}
    .stage {{ position: absolute; left: 0; top: 0; transform-origin: top left; background: #fff; }}
    .node {{ position: absolute; min-width: 0; min-height: 0; }}
    .node.image, .node.shape, .node.layer {{ overflow: hidden; }}
    .node.group {{ overflow: visible; }}
    .node img {{ display: block; width: 100%; height: 100%; object-fit: fill; }}
    .node.text {{ white-space: pre-wrap; overflow: visible; line-height: 1.1; }}
  </style>
</head>
<body>
  <div class="viewport" id="viewport">
    <div class="stage" id="stage"></div>
  </div>
  <script type="application/json" id="scene-data">{_script_safe_json(render_data)}</script>
  <script>
    (() => {{
      const data = JSON.parse(document.getElementById('scene-data').textContent);
      const stage = document.getElementById('stage');
      const viewport = document.getElementById('viewport');
      const nodes = data.nodes || [];
      stage.style.width = `${{data.scene.width}}px`;
      stage.style.height = `${{data.scene.height}}px`;

      const root = {{ id: data.root_node_id }};
      const childrenByParent = new Map();
      nodes.filter((node) => node.type !== 'root').forEach((node) => {{
        const parentId = node.parent_id || root.id;
        const items = childrenByParent.get(parentId) || [];
        items.push(node);
        childrenByParent.set(parentId, items);
      }});
      for (const items of childrenByParent.values()) {{
        items.sort((a, b) => (a.order_index || 0) - (b.order_index || 0));
      }}

      function colorFrom(value) {{
        if (Array.isArray(value)) {{
          const [r, g, b] = value;
          return `rgb(${{Math.round(r || 0)}}, ${{Math.round(g || 0)}}, ${{Math.round(b || 0)}})`;
        }}
        if (value && typeof value === 'object') {{
          const channel = (name) => Math.round((value[name] ?? 0) * (value[name + '_scale'] === 255 ? 1 : 255));
          return `rgb(${{channel('r')}}, ${{channel('g')}}, ${{channel('b')}})`;
        }}
        return null;
      }}

      function renderNode(node) {{
        const el = document.createElement('div');
        el.className = `node ${{node.type || 'layer'}}`;
        const t = node.transform || {{}};
        el.style.left = `${{t.x || 0}}px`;
        el.style.top = `${{t.y || 0}}px`;
        el.style.width = `${{t.width || 0}}px`;
        el.style.height = `${{t.height || 0}}px`;
        el.style.opacity = String(node.opacity ?? 1);
        if (node.visible === false) el.style.display = 'none';
        const transforms = [];
        if (t.rotation) transforms.push(`rotate(${{t.rotation}}deg)`);
        if (t.scale_x !== undefined && t.scale_y !== undefined && (t.scale_x !== 1 || t.scale_y !== 1)) {{
          transforms.push(`scale(${{t.scale_x}}, ${{t.scale_y}})`);
        }}
        if (transforms.length) el.style.transform = transforms.join(' ');

        if (node.asset_file) {{
          const img = document.createElement('img');
          img.src = node.asset_file;
          img.alt = node.name || '';
          img.draggable = false;
          el.appendChild(img);
        }} else if (node.type === 'text') {{
          const props = node.text_properties || {{}};
          el.textContent = props.text || node.name || '';
          if (props.font_size) el.style.fontSize = `${{props.font_size}}px`;
          if (props.font_name) el.style.fontFamily = `'${{props.font_name}}', sans-serif`;
          const color = colorFrom(props.fill_color);
          if (color) el.style.color = color;
          if (props.faux_bold) el.style.fontWeight = '700';
          if (props.faux_italic) el.style.fontStyle = 'italic';
        }}

        const children = childrenByParent.get(node.id) || [];
        children.forEach((child) => el.appendChild(renderNode(child)));
        return el;
      }}

      const rootChildren = childrenByParent.get(root.id) || [];
      rootChildren.forEach((child) => stage.appendChild(renderNode(child)));

      function fit() {{
        const scale = Math.min(
          (window.innerWidth - 48) / data.scene.width,
          (window.innerHeight - 48) / data.scene.height,
          1
        );
        viewport.style.width = `${{data.scene.width * scale}}px`;
        viewport.style.height = `${{data.scene.height * scale}}px`;
        stage.style.transform = `scale(${{scale}})`;
      }}
      fit();
      window.addEventListener('resize', fit);
    }})();
  </script>
</body>
</html>"""

    def _escape_html(self, value: str) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )


def project_name_from_data(scene_data: dict) -> str:
    metadata = (scene_data.get("scene") or {}).get("metadata") or {}
    return str(metadata.get("source_name") or "Ubiqx HTML5 Export")


def run_export_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(ExportJob, job_id)
        if job is None or job.status in TERMINAL_STATUSES:
            return
        job.status = "running"
        job.started_at = _now()
        db.commit()

        project = db.get(Project, job.project_id)
        if project is None:
            raise ExportFailure("project_missing")
        scene = db.get(Scene, project.root_scene_id) if project.root_scene_id else None
        if scene is None:
            raise ExportFailure("scene_missing")

        package_path, _export_dir, manifest, warnings = HTML5ExportService(db).export(project, scene)
        job.output_path = str(package_path)
        job.manifest = manifest
        job.warnings = warnings
        job.status = "succeeded"
        job.finished_at = _now()
        project.last_autosaved_at = _now()
        project.updated_at = _now()
        db.commit()
    except ExportFailure as exc:
        db.rollback()
        _mark_failed(db, job_id, str(exc))
    except Exception as exc:
        db.rollback()
        _mark_failed(db, job_id, f"export_failed: {type(exc).__name__}")
    finally:
        db.close()


def _mark_failed(db: Session, job_id: str, error: str) -> None:
    job = db.get(ExportJob, job_id)
    if job is None:
        return
    job.status = "failed"
    job.error = error
    job.finished_at = _now()
    db.commit()
