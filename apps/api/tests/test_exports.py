from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ExportJob, SceneNode


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
TERMINAL = {"succeeded", "failed", "cancelled"}


def _create_project(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/api/v1/projects", headers=headers, json={"name": "Export Test"})
    assert response.status_code == 201
    return response.json()["id"]


def _upload_fixture(client: TestClient, headers: dict[str, str], project_id: str, filename: str) -> str:
    source_path = FIXTURE_DIR / filename
    response = client.post(
        f"/api/v1/projects/{project_id}/assets",
        headers=headers,
        files={"file": (filename, source_path.read_bytes(), "image/vnd.adobe.photoshop")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _import_basic_psd(client: TestClient, headers: dict[str, str], project_id: str) -> None:
    source_asset_id = _upload_fixture(client, headers, project_id, "basic.psd")
    response = client.post(
        f"/api/v1/projects/{project_id}/imports",
        headers=headers,
        json={"source_asset_id": source_asset_id, "adapter": "psd"},
    )
    assert response.status_code == 201
    _wait_for_terminal(client, headers, f"/api/v1/imports/{response.json()['id']}")


def _wait_for_terminal(client: TestClient, headers: dict[str, str], path: str) -> dict:
    for _ in range(80):
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        body = response.json()
        if body["status"] in TERMINAL:
            return body
        time.sleep(0.05)
    pytest.fail("job did not reach a terminal state")


def _add_effect_metadata(scene_id: str) -> None:
    db = SessionLocal()
    try:
        node = db.scalar(
            select(SceneNode)
            .where(SceneNode.scene_id == scene_id, SceneNode.type != "root")
            .limit(1)
        )
        assert node is not None
        node.effect_metadata = {"effects": "BevelEmboss"}
        db.commit()
    finally:
        db.close()


def test_export_imported_scene_as_html5_package(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    _import_basic_psd(client, auth_headers, project_id)

    response = client.post(
        f"/api/v1/projects/{project_id}/exports",
        headers=auth_headers,
        json={"target": "html5"},
    )
    assert response.status_code == 201
    export_id = response.json()["id"]
    job = _wait_for_terminal(client, auth_headers, f"/api/v1/exports/{export_id}")
    assert job["status"] == "succeeded"
    assert job["error"] is None
    assert job["warnings"] == []

    manifest = job["manifest"]
    assert manifest["validation"]["passed"] is True
    assert manifest["validation"]["node_count"] == 3
    assert manifest["validation"]["asset_count"] == 2
    assert "index.html" in manifest["files"]
    assert "scene.json" in manifest["files"]
    assert any(path.startswith("assets/") for path in manifest["files"])

    download = client.get(f"/api/v1/exports/{export_id}/download", headers=auth_headers)
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert {"index.html", "scene.json", "manifest.json"}.issubset(names)
        assert any(name.startswith("assets/") for name in names)
        html = archive.read("index.html").decode("utf-8")
        assert "HUD" in html
        assert "Button" in html
        assert "Background" in html

    preview = client.get(f"/api/v1/exports/{export_id}/preview", headers=auth_headers)
    assert preview.status_code == 200
    assert "text/html" in preview.headers["content-type"]
    assert "data:image/png;base64," in preview.text
    assert "HUD" in preview.text


def test_export_title_uses_project_name(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    rename = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={"name": "Project Display Name"},
    )
    assert rename.status_code == 200
    node = client.post(
        f"/api/v1/projects/{project_id}/scene/nodes",
        headers=auth_headers,
        json={"type": "shape", "name": "Panel"},
    )
    assert node.status_code == 201

    response = client.post(
        f"/api/v1/projects/{project_id}/exports",
        headers=auth_headers,
        json={"target": "html5"},
    )
    assert response.status_code == 201
    job = _wait_for_terminal(client, auth_headers, f"/api/v1/exports/{response.json()['id']}")
    assert job["status"] == "succeeded"

    preview = client.get(
        f"/api/v1/exports/{response.json()['id']}/preview",
        headers=auth_headers,
    )
    assert preview.status_code == 200
    assert "<title>Project Display Name</title>" in preview.text


def test_exports_keep_immutable_job_outputs(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    node = client.post(
        f"/api/v1/projects/{project_id}/scene/nodes",
        headers=auth_headers,
        json={"type": "shape", "name": "Panel"},
    )
    assert node.status_code == 201

    export_ids: list[str] = []
    for _ in range(2):
        response = client.post(
            f"/api/v1/projects/{project_id}/exports",
            headers=auth_headers,
            json={"target": "html5"},
        )
        assert response.status_code == 201
        export_ids.append(response.json()["id"])
        job = _wait_for_terminal(client, auth_headers, f"/api/v1/exports/{export_ids[-1]}")
        assert job["status"] == "succeeded"

    db = SessionLocal()
    try:
        jobs = [db.get(ExportJob, export_id) for export_id in export_ids]
        assert all(job is not None and job.output_path for job in jobs)
        assert jobs[0].output_path != jobs[1].output_path
    finally:
        db.close()


def test_empty_scene_cannot_export(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    response = client.post(
        f"/api/v1/projects/{project_id}/exports",
        headers=auth_headers,
        json={"target": "html5"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "scene_empty"


def test_export_reports_unsupported_effects(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    _import_basic_psd(client, auth_headers, project_id)
    scene = client.get(f"/api/v1/projects/{project_id}/scene", headers=auth_headers).json()
    _add_effect_metadata(scene["id"])

    response = client.post(
        f"/api/v1/projects/{project_id}/exports",
        headers=auth_headers,
        json={"target": "html5"},
    )
    assert response.status_code == 201
    job = _wait_for_terminal(client, auth_headers, f"/api/v1/exports/{response.json()['id']}")
    assert job["status"] == "succeeded"
    assert any(warning["code"] == "unsupported_visual_effect" for warning in job["warnings"])


def test_export_derives_viewport_from_content_bounds(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)

    def add_node(name: str, transform: dict) -> None:
        response = client.post(
            f"/api/v1/projects/{project_id}/scene/nodes",
            headers=auth_headers,
            json={"type": "shape", "name": name, "transform": transform},
        )
        assert response.status_code == 201

    add_node("A", {"x": 100, "y": 100, "width": 50, "height": 50})
    add_node("B", {"x": -200, "y": -300, "width": 40, "height": 40})

    response = client.post(
        f"/api/v1/projects/{project_id}/exports",
        headers=auth_headers,
        json={"target": "html5"},
    )
    assert response.status_code == 201
    export_id = response.json()["id"]
    job = _wait_for_terminal(client, auth_headers, f"/api/v1/exports/{export_id}")
    assert job["status"] == "succeeded"

    # Content spans x: [-200, 150] and y: [-300, 150]; the exported viewport is
    # that bounding box plus EXPORT_PADDING (24) on every side.
    scene = job["manifest"]["scene"]
    assert scene["width"] == pytest.approx((150 - (-200)) + 48)
    assert scene["height"] == pytest.approx((150 - (-300)) + 48)

    download = client.get(f"/api/v1/exports/{export_id}/download", headers=auth_headers)
    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        scene_json = json.loads(archive.read("scene.json").decode("utf-8"))
    nodes_by_name = {node["name"]: node for node in scene_json["nodes"]}
    assert nodes_by_name["B"]["transform"]["x"] == pytest.approx(-200)
    assert nodes_by_name["B"]["transform"]["y"] == pytest.approx(-300)
    assert scene["offset"]["x"] == pytest.approx(224)
    assert scene["offset"]["y"] == pytest.approx(324)
