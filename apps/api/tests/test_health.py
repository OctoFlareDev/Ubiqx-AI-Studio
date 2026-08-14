from fastapi.testclient import TestClient

from app.main import ready
from sqlalchemy.exc import SQLAlchemyError


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_readiness_reports_database_failure_without_500() -> None:
    class FailingDatabase:
        def execute(self, _query):
            raise SQLAlchemyError("database unavailable")

    response = ready(FailingDatabase())
    assert response.status_code == 503
    assert b'"database":"error"' in response.body


def test_openapi_available(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Ubiqx AI Studio API"
