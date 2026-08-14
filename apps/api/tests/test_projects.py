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


def test_project_names_must_not_be_blank(client: TestClient, auth_headers: dict[str, str]) -> None:
    create_response = client.post("/api/v1/projects", headers=auth_headers, json={"name": "   "})
    assert create_response.status_code == 400

    project = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"name": "Valid Name"},
    ).json()
    update_response = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=auth_headers,
        json={"name": "\t"},
    )
    assert update_response.status_code == 400


def test_project_list_supports_cursor_pagination(client: TestClient, auth_headers: dict[str, str]) -> None:
    for index in range(3):
        response = client.post(
            "/api/v1/projects",
            headers=auth_headers,
            json={"name": f"Page {index}"},
        )
        assert response.status_code == 201

    first = client.get("/api/v1/projects?limit=2", headers=auth_headers)
    assert first.status_code == 200
    first_body = first.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"] is not None

    second = client.get(
        f"/api/v1/projects?limit=2&cursor={first_body['next_cursor']}",
        headers=auth_headers,
    )
    assert second.status_code == 200
    assert len(second.json()["items"]) >= 1

    invalid = client.get("/api/v1/projects?cursor=not-a-cursor", headers=auth_headers)
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_cursor"


def test_project_updates_require_a_fresh_version_when_supplied(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    created = client.post("/api/v1/projects", headers=auth_headers, json={"name": "Versioned Project"})
    assert created.status_code == 201
    project = created.json()
    assert project["version"] == 1
    assert created.headers["etag"] == '"1"'

    updated = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers={**auth_headers, "If-Match": '"1"'},
        json={"name": "Fresh Update"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.headers["etag"] == '"2"'

    stale = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers={**auth_headers, "If-Match": '"1"'},
        json={"name": "Stale Update"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_version"
