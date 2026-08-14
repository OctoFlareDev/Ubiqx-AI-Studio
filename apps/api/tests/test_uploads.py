from fastapi.testclient import TestClient


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
)


def _create_project(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/api/v1/projects", headers=headers, json={"name": "Upload Test"})
    return response.json()["id"]


def test_upload_and_deduplicate_png(client: TestClient, auth_headers: dict[str, str]) -> None:
    project_id = _create_project(client, auth_headers)
    files = {"file": ("button.png", PNG_BYTES, "image/png")}
    first = client.post(f"/api/v1/projects/{project_id}/assets", headers=auth_headers, files=files)
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["media_type"] == "image/png"

    second = client.post(f"/api/v1/projects/{project_id}/assets", headers=auth_headers, files=files)
    assert second.status_code == 201
    assert second.json()["id"] == first_body["id"]

    assets = client.get(f"/api/v1/projects/{project_id}/assets", headers=auth_headers)
    assert assets.status_code == 200
    assert len(assets.json()) == 1

    download = client.get(f"/api/v1/assets/{first_body['id']}/content", headers=auth_headers)
    assert download.status_code == 200
    assert download.content == PNG_BYTES


def test_upload_rejects_wrong_extension(client: TestClient, auth_headers: dict[str, str]) -> None:
    project_id = _create_project(client, auth_headers)
    files = {"file": ("not-a-png.png", b"plain text", "image/png")}
    response = client.post(f"/api/v1/projects/{project_id}/assets", headers=auth_headers, files=files)
    assert response.status_code == 400
    assert response.json()["error"]["code"] in {"file_extension_mismatch", "unknown_file_type"}


def test_upload_rejects_unsupported_extension(client: TestClient, auth_headers: dict[str, str]) -> None:
    project_id = _create_project(client, auth_headers)
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    response = client.post(f"/api/v1/projects/{project_id}/assets", headers=auth_headers, files=files)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_asset_delete_rejects_referenced_assets(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project_id = _create_project(client, auth_headers)
    upload = client.post(
        f"/api/v1/projects/{project_id}/assets",
        headers=auth_headers,
        files={"file": ("button.png", PNG_BYTES, "image/png")},
    )
    asset_id = upload.json()["id"]
    scene = client.get(f"/api/v1/projects/{project_id}/scene", headers=auth_headers).json()
    node = client.post(
        f"/api/v1/projects/{project_id}/scene/nodes",
        headers=auth_headers,
        json={"type": "image", "name": "Button", "asset_id": asset_id},
    )
    assert node.status_code == 201

    blocked = client.delete(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "asset_in_use"

    removed_node = client.delete(
        f"/api/v1/scenes/{scene['id']}/nodes/{node.json()['id']}",
        headers=auth_headers,
    )
    assert removed_node.status_code == 204
    deleted = client.delete(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    assert deleted.status_code == 204
