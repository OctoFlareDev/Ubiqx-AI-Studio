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
