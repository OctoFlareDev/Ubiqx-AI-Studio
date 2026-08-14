import json
from pathlib import Path

from fastapi.testclient import TestClient


CONTRACT_PATH = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "openapi.json"


def test_openapi_matches_committed_contract(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    generated = response.json()
    committed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert generated == committed, "Route or schema drift: regenerate with `make contract`"


def test_openapi_generation_is_reproducible(client: TestClient) -> None:
    first = client.get("/openapi.json").json()
    second = client.get("/openapi.json").json()
    assert first == second


def test_contract_covers_expected_resources(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    expected = {
        "/api/v1/projects": {"get", "post"},
        "/api/v1/projects/{project_id}": {"get", "patch", "delete"},
        "/api/v1/projects/{project_id}/assets": {"get", "post"},
        "/api/v1/projects/{project_id}/imports": {"post"},
        "/api/v1/projects/{project_id}/exports": {"post"},
        "/api/v1/projects/{project_id}/ai-tasks": {"get", "post"},
        "/api/v1/api-keys": {"get", "post"},
        "/api/v1/assets/{asset_id}/content": {"get"},
        "/api/v1/exports/{export_id}/download": {"get"},
    }
    for path, methods in expected.items():
        assert path in paths, f"contract missing path: {path}"
        assert methods.issubset(set(paths[path])), f"contract missing methods for {path}"


def test_contract_documents_stable_error_envelope(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "ErrorEnvelope" in schema["components"]["schemas"]
    error_codes = {"400", "401", "403", "404", "409", "429", "500"}

    for path, path_item in schema["paths"].items():
        if not path.startswith("/api/v1/"):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            responses = operation["responses"]
            assert "422" not in responses
            for code in error_codes:
                response = responses[code]
                assert response["content"]["application/json"]["schema"] == {
                    "$ref": "#/components/schemas/ErrorEnvelope"
                }
