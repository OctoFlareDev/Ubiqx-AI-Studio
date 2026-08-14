from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
TERMINAL = {"succeeded", "failed", "cancelled"}


def _create_project(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/api/v1/projects", headers=headers, json={"name": "Fixture Matrix"})
    assert response.status_code == 201
    return response.json()["id"]


def _wait_for_import(client: TestClient, headers: dict[str, str], import_id: str) -> dict:
    for _ in range(100):
        body = client.get(f"/api/v1/imports/{import_id}", headers=headers).json()
        if body["status"] in TERMINAL:
            return body
        time.sleep(0.03)
    pytest.fail("fixture import did not reach a terminal state")


def test_documented_fixture_matrix_is_checked_in() -> None:
    expected = {
        "basic.psd",
        "basic.psb",
        "malformed.psd",
        "oversized.psd",
        "sample.jpg",
        "sample.svg",
        "sample.webp",
        "transparent.png",
        "low-resolution.png",
    }
    assert expected.issubset({path.name for path in FIXTURE_DIR.iterdir()})


@pytest.mark.parametrize(
    ("filename", "media_type"),
    [
        ("sample.jpg", "image/jpeg"),
        ("sample.webp", "image/webp"),
        ("transparent.png", "image/png"),
        ("sample.svg", "image/svg+xml"),
    ],
)
def test_raster_fixture_uploads_preserve_detected_metadata(
    client: TestClient,
    auth_headers: dict[str, str],
    filename: str,
    media_type: str,
) -> None:
    project_id = _create_project(client, auth_headers)
    path = FIXTURE_DIR / filename
    response = client.post(
        f"/api/v1/projects/{project_id}/assets",
        headers=auth_headers,
        files={"file": (filename, path.read_bytes(), media_type)},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["media_type"] == media_type
    assert body["width"] is not None
    assert body["height"] is not None


def test_oversized_psd_fixture_reports_downsampling(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    path = FIXTURE_DIR / "oversized.psd"
    upload = client.post(
        f"/api/v1/projects/{project_id}/assets",
        headers=auth_headers,
        files={"file": (path.name, path.read_bytes(), "image/vnd.adobe.photoshop")},
    )
    assert upload.status_code == 201
    import_response = client.post(
        f"/api/v1/projects/{project_id}/imports",
        headers=auth_headers,
        json={"source_asset_id": upload.json()["id"], "adapter": "psd"},
    )
    assert import_response.status_code == 201
    job = _wait_for_import(client, auth_headers, import_response.json()["id"])
    assert job["status"] == "succeeded"
    assert any(item["code"] == "document_downsampled" for item in job["warnings"])


def test_malformed_psd_fixture_fails_without_scene_mutation(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    path = FIXTURE_DIR / "malformed.psd"
    upload = client.post(
        f"/api/v1/projects/{project_id}/assets",
        headers=auth_headers,
        files={"file": (path.name, path.read_bytes(), "image/vnd.adobe.photoshop")},
    )
    assert upload.status_code == 201
    import_response = client.post(
        f"/api/v1/projects/{project_id}/imports",
        headers=auth_headers,
        json={"source_asset_id": upload.json()["id"], "adapter": "psd"},
    )
    assert import_response.status_code == 201
    job = _wait_for_import(client, auth_headers, import_response.json()["id"])
    assert job["status"] == "failed"
    assert job["error"] == "invalid_psd_file"
