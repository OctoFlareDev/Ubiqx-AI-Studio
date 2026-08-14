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
