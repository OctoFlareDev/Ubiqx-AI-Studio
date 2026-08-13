from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
TERMINAL = {"succeeded", "failed", "cancelled"}


def _create_project(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/api/v1/projects", headers=headers, json={"name": "Import Test"})
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


def _wait_for_terminal(client: TestClient, headers: dict[str, str], import_id: str) -> dict:
    for _ in range(80):
        response = client.get(f"/api/v1/imports/{import_id}", headers=headers)
        assert response.status_code == 200
        body = response.json()
        if body["status"] in TERMINAL:
            return body
        time.sleep(0.05)
    pytest.fail("import job did not reach a terminal state")


def test_import_psd_creates_scene_graph(client: TestClient, auth_headers: dict[str, str]) -> None:
    project_id = _create_project(client, auth_headers)
    source_asset_id = _upload_fixture(client, auth_headers, project_id, "basic.psd")

    response = client.post(
        f"/api/v1/projects/{project_id}/imports",
        headers=auth_headers,
        json={"source_asset_id": source_asset_id, "adapter": "psd"},
    )
    assert response.status_code == 201
    import_id = response.json()["id"]
    job = _wait_for_terminal(client, auth_headers, import_id)
    assert job["status"] == "succeeded"
    assert job["error"] is None
    assert job["warnings"] == []

    scene = client.get(f"/api/v1/projects/{project_id}/scene", headers=auth_headers)
    assert scene.status_code == 200
    assert scene.json()["width"] == 160
    assert scene.json()["height"] == 100

    nodes = client.get(f"/api/v1/scenes/{scene.json()['id']}/nodes", headers=auth_headers)
    assert nodes.status_code == 200
    node_list = nodes.json()
    assert {node["type"] for node in node_list} == {"root", "group", "image"}
    assert {node["name"] for node in node_list} == {"Root", "Background", "HUD", "Button"}

    group = next(node for node in node_list if node["name"] == "HUD")
    button = next(node for node in node_list if node["name"] == "Button")
    background = next(node for node in node_list if node["name"] == "Background")
    assert button["parent_id"] == group["id"]
    assert group["parent_id"] == scene.json()["root_node_id"]
    assert background["asset_id"]
    assert button["asset_id"]

    assets = client.get(f"/api/v1/projects/{project_id}/assets", headers=auth_headers)
    assert assets.status_code == 200
    assert len(assets.json()) >= 3
    imported = [asset for asset in assets.json() if asset["source"] == "psd_import"]
    assert len(imported) == 2


def test_import_psb_uses_same_adapter(client: TestClient, auth_headers: dict[str, str]) -> None:
    project_id = _create_project(client, auth_headers)
    source_asset_id = _upload_fixture(client, auth_headers, project_id, "basic.psb")

    response = client.post(
        f"/api/v1/projects/{project_id}/imports",
        headers=auth_headers,
        json={"source_asset_id": source_asset_id, "adapter": "psd"},
    )
    assert response.status_code == 201
    job = _wait_for_terminal(client, auth_headers, response.json()["id"])
    assert job["status"] == "succeeded"


def test_failed_import_does_not_replace_scene(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    malformed = b"8BPS\x00\x01" + b"\x00" * 128
    upload = client.post(
        f"/api/v1/projects/{project_id}/assets",
        headers=auth_headers,
        files={"file": ("malformed.psd", malformed, "image/vnd.adobe.photoshop")},
    )
    assert upload.status_code == 201
    source_asset_id = upload.json()["id"]

    import_response = client.post(
        f"/api/v1/projects/{project_id}/imports",
        headers=auth_headers,
        json={"source_asset_id": source_asset_id, "adapter": "psd"},
    )
    assert import_response.status_code == 201
    job = _wait_for_terminal(client, auth_headers, import_response.json()["id"])
    assert job["status"] == "failed"
    assert job["error"] == "invalid_psd_file"

    scene = client.get(f"/api/v1/projects/{project_id}/scene", headers=auth_headers)
    nodes = client.get(f"/api/v1/scenes/{scene.json()['id']}/nodes", headers=auth_headers)
    assert [node["type"] for node in nodes.json()] == ["root"]


def test_cancel_queued_import(client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = _create_project(client, auth_headers)
    source_asset_id = _upload_fixture(client, auth_headers, project_id, "basic.psd")
    monkeypatch.setattr("app.main.run_import_job", lambda _job_id: None)

    import_response = client.post(
        f"/api/v1/projects/{project_id}/imports",
        headers=auth_headers,
        json={"source_asset_id": source_asset_id, "adapter": "psd"},
    )
    import_id = import_response.json()["id"]
    cancel_response = client.post(f"/api/v1/imports/{import_id}/cancel", headers=auth_headers)
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    get_response = client.get(f"/api/v1/imports/{import_id}", headers=auth_headers)
    assert get_response.json()["status"] == "cancelled"

