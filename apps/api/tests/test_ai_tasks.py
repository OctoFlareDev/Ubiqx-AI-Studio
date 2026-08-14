from __future__ import annotations

import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.ai_service import AiTaskFailure, LocalImageProvider


TERMINAL = {"succeeded", "failed", "cancelled"}


def _create_project(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/api/v1/projects", headers=headers, json={"name": "AI Test"})
    assert response.status_code == 201
    return response.json()["id"]


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _upload_png(client: TestClient, headers: dict[str, str], project_id: str, image: Image.Image) -> str:
    response = client.post(
        f"/api/v1/projects/{project_id}/assets",
        headers=headers,
        files={"file": ("input.png", _png_bytes(image), "image/png")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _wait_for_terminal(client: TestClient, headers: dict[str, str], task_id: str) -> dict:
    for _ in range(100):
        response = client.get(f"/api/v1/ai-tasks/{task_id}", headers=headers)
        assert response.status_code == 200
        body = response.json()
        if body["status"] in TERMINAL:
            return body
        time.sleep(0.03)
    pytest.fail("AI task did not reach a terminal state")


def test_upscale_task_creates_processed_asset(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    input_asset_id = _upload_png(
        client,
        auth_headers,
        project_id,
        Image.new("RGBA", (2, 2), (220, 40, 40, 255)),
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/ai-tasks",
        headers=auth_headers,
        json={
            "operation": "upscale",
            "provider": "local",
            "input_asset_id": input_asset_id,
            "options": {"scale": 2},
        },
    )
    assert response.status_code == 201
    task = _wait_for_terminal(client, auth_headers, response.json()["id"])
    assert task["status"] == "succeeded"
    assert task["retry_count"] == 0
    assert task["last_error"] is None
    assert task["output_asset_id"]

    output_asset = client.get(f"/api/v1/assets/{task['output_asset_id']}", headers=auth_headers)
    assert output_asset.status_code == 200
    assert output_asset.json()["source"] == "ai_processed"
    assert output_asset.json()["width"] == 4
    assert output_asset.json()["height"] == 4


def test_remove_background_task_creates_alpha_asset(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    image = Image.new("RGBA", (4, 4), (255, 255, 255, 255))
    pixels = image.load()
    for x, y in [(1, 1), (2, 1), (1, 2), (2, 2)]:
        pixels[x, y] = (230, 40, 40, 255)
    input_asset_id = _upload_png(client, auth_headers, project_id, image)

    response = client.post(
        f"/api/v1/projects/{project_id}/ai-tasks",
        headers=auth_headers,
        json={
            "operation": "remove_background",
            "provider": "local",
            "input_asset_id": input_asset_id,
            "options": {},
        },
    )
    assert response.status_code == 201
    task = _wait_for_terminal(client, auth_headers, response.json()["id"])
    assert task["status"] == "succeeded"

    output = client.get(f"/api/v1/assets/{task['output_asset_id']}/content", headers=auth_headers)
    assert output.status_code == 200
    processed = Image.open(io.BytesIO(output.content)).convert("RGBA")
    assert processed.getpixel((0, 0))[3] == 0
    assert processed.getpixel((1, 1))[3] == 255


def test_retry_limit_exhausts_without_infinite_retry(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(self: LocalImageProvider, request: object) -> None:
        raise AiTaskFailure("provider_timeout", "provider_timeout", retryable=True)

    monkeypatch.setattr(LocalImageProvider, "process", fail)
    project_id = _create_project(client, auth_headers)
    input_asset_id = _upload_png(
        client,
        auth_headers,
        project_id,
        Image.new("RGBA", (2, 2), (10, 20, 30, 255)),
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/ai-tasks",
        headers=auth_headers,
        json={
            "operation": "upscale",
            "provider": "local",
            "input_asset_id": input_asset_id,
            "options": {"scale": 2},
        },
    )
    task = _wait_for_terminal(client, auth_headers, response.json()["id"])
    assert task["status"] == "failed"
    assert task["retry_count"] == 2
    assert task["last_error"] == "provider_timeout"
    assert task["output_asset_id"] is None


def test_cancel_queued_ai_task(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.main.run_ai_task", lambda _task_id: None)
    project_id = _create_project(client, auth_headers)
    input_asset_id = _upload_png(
        client,
        auth_headers,
        project_id,
        Image.new("RGBA", (2, 2), (10, 20, 30, 255)),
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/ai-tasks",
        headers=auth_headers,
        json={
            "operation": "upscale",
            "provider": "local",
            "input_asset_id": input_asset_id,
            "options": {"scale": 2},
        },
    )
    task_id = response.json()["id"]
    cancel = client.post(f"/api/v1/ai-tasks/{task_id}/cancel", headers=auth_headers)
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    get = client.get(f"/api/v1/ai-tasks/{task_id}", headers=auth_headers)
    assert get.json()["status"] == "cancelled"


def test_unsupported_ai_input_fails_cleanly(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"></svg>'
    upload = client.post(
        f"/api/v1/projects/{project_id}/assets",
        headers=auth_headers,
        files={"file": ("vector.svg", svg, "image/svg+xml")},
    )
    assert upload.status_code == 201

    response = client.post(
        f"/api/v1/projects/{project_id}/ai-tasks",
        headers=auth_headers,
        json={
            "operation": "remove_background",
            "provider": "local",
            "input_asset_id": upload.json()["id"],
            "options": {},
        },
    )
    task = _wait_for_terminal(client, auth_headers, response.json()["id"])
    assert task["status"] == "failed"
    assert task["retry_count"] == 0
    assert task["last_error"] == "unsupported_ai_input_type"


def test_unregistered_ai_provider_is_rejected_at_creation(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    input_asset_id = _upload_png(
        client,
        auth_headers,
        project_id,
        Image.new("RGBA", (2, 2), (10, 20, 30, 255)),
    )
    response = client.post(
        f"/api/v1/projects/{project_id}/ai-tasks",
        headers=auth_headers,
        json={
            "operation": "upscale",
            "provider": "openai",
            "input_asset_id": input_asset_id,
            "options": {},
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
