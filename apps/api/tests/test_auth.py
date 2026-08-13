from fastapi.testclient import TestClient


def test_bootstrap_creates_local_session(client: TestClient) -> None:
    response = client.post("/api/v1/auth/bootstrap")
    assert response.status_code == 200
    body = response.json()
    assert body["api_key"].startswith("ubq_")
    assert body["user"]["display_name"] == "Local Designer"


def test_profile_requires_valid_key(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/auth/profile", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"]


def test_profile_rejects_missing_key(client: TestClient) -> None:
    response = client.get("/api/v1/auth/profile")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"

