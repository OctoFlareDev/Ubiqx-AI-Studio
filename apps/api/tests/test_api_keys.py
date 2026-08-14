from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.models import ApiKey


def _create_scoped_key(client: TestClient, auth_headers: dict[str, str], scopes: list[str]) -> tuple[str, str]:
    response = client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "scoped-test-key", "scopes": scopes},
    )
    assert response.status_code == 201
    body = response.json()
    return body["api_key"], body["key"]["id"]


def test_create_list_and_revoke_api_key(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Agent Key", "scopes": ["projects:read"]},
    )
    assert created.status_code == 201
    body = created.json()
    raw_key = body["api_key"]
    key_id = body["key"]["id"]
    assert raw_key.startswith("ubq_")
    assert body["key"]["name"] == "Agent Key"
    assert body["key"]["scopes"] == ["projects:read"]
    assert body["key"]["revoked_at"] is None

    db = SessionLocal()
    try:
        stored = db.get(ApiKey, key_id)
        assert stored is not None
        assert "$" in stored.key_hash
        assert raw_key not in stored.key_hash
    finally:
        db.close()

    listing = client.get("/api/v1/api-keys", headers=auth_headers)
    assert listing.status_code == 200
    assert any(item["id"] == key_id for item in listing.json()["items"])

    new_headers = {"Authorization": f"Bearer {raw_key}"}
    assert client.get("/api/v1/auth/profile", headers=new_headers).status_code == 200

    revoked = client.post(f"/api/v1/api-keys/{key_id}/revoke", headers=auth_headers)
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None

    assert client.get("/api/v1/auth/profile", headers=new_headers).status_code == 401


def test_scoped_key_cannot_access_unauthorized_resources(
    client: TestClient, auth_headers: dict[str, str],
) -> None:
    raw_key, _ = _create_scoped_key(client, auth_headers, ["projects:read"])
    headers = {"Authorization": f"Bearer {raw_key}"}

    allowed = client.get("/api/v1/projects", headers=headers)
    assert allowed.status_code == 200

    denied = client.post("/api/v1/projects", headers=headers, json={"name": "Nope"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "insufficient_scope"

    denied_other_family = client.get("/api/v1/api-keys", headers=headers)
    assert denied_other_family.status_code == 403


def test_api_key_rejects_unknown_scope(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Bad", "scopes": ["bogus:read"]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unknown_scope"


def test_api_keys_endpoints_require_admin_scope(client: TestClient, auth_headers: dict[str, str]) -> None:
    raw_key, _ = _create_scoped_key(client, auth_headers, ["projects:read"])
    headers = {"Authorization": f"Bearer {raw_key}"}

    assert client.get("/api/v1/api-keys", headers=headers).status_code == 403
    assert client.post("/api/v1/api-keys", headers=headers, json={"name": "x"}).status_code == 403
