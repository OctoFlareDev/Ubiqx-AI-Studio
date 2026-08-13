from fastapi.testclient import TestClient


def test_project_crud(client: TestClient, auth_headers: dict[str, str]) -> None:
    create_response = client.post("/api/v1/projects", headers=auth_headers, json={"name": "Main Menu"})
    assert create_response.status_code == 201
    project = create_response.json()
    project_id = project["id"]
    assert project["name"] == "Main Menu"
    assert project["root_scene_id"]

    list_response = client.get("/api/v1/projects", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(item["id"] == project_id for item in list_response.json()["items"])

    patch_response = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={"name": "Main Menu Renamed"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "Main Menu Renamed"

    archive_response = client.post(f"/api/v1/projects/{project_id}/archive", headers=auth_headers)
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    restore_response = client.post(f"/api/v1/projects/{project_id}/restore", headers=auth_headers)
    assert restore_response.status_code == 200
    assert restore_response.json()["status"] == "active"

    delete_response = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_project_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/projects")
    assert response.status_code == 401


def test_project_validation(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/v1/projects", headers=auth_headers, json={"name": ""})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"

