from fastapi.testclient import TestClient
import time

from app.main import app
from app.rate_limit import SlidingWindowRateLimiter


def test_rate_limit_returns_structured_error(client: TestClient, auth_headers: dict[str, str]) -> None:
    original = app.state.rate_limiter
    app.state.rate_limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60)
    try:
        for _ in range(3):
            response = client.get("/api/v1/projects", headers=auth_headers)
            assert response.status_code == 200

        limited = client.get("/api/v1/projects", headers=auth_headers)
        assert limited.status_code == 429
        body = limited.json()
        assert body["error"]["code"] == "rate_limited"
        assert body["error"]["request_id"]
        assert int(limited.headers["Retry-After"]) >= 1
    finally:
        app.state.rate_limiter = original


def test_health_is_not_rate_limited(client: TestClient) -> None:
    original = app.state.rate_limiter
    app.state.rate_limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)
    try:
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200
    finally:
        app.state.rate_limiter = original


def test_expired_identity_windows_are_periodically_removed() -> None:
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=0.01)
    for index in range(63):
        assert limiter.allow(f"expired-{index}")
    time.sleep(0.02)
    assert limiter.allow("cleanup-trigger")
    assert len(limiter._hits) == 1
    assert "cleanup-trigger" in limiter._hits
