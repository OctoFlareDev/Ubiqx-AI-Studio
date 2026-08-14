from __future__ import annotations

import time
import uuid

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.models import SceneNode


TERMINAL = {"succeeded", "failed", "cancelled"}


def _seed_nodes(client: TestClient, headers: dict[str, str], count: int) -> tuple[dict, dict]:
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Perf Test"}).json()
    scene = client.get(f"/api/v1/projects/{project['id']}/scene", headers=headers).json()
    db = SessionLocal()
    try:
        for index in range(count):
            db.add(SceneNode(
                id=str(uuid.uuid4()),
                scene_id=scene["id"],
                parent_id=scene["root_node_id"],
                type="shape",
                name=f"node-{index}",
                transform={"x": index % 1000, "y": index % 800, "width": 12, "height": 12},
                order_index=index,
            ))
        db.commit()
    finally:
        db.close()
    return project, scene


def test_list_nodes_performance(client: TestClient, auth_headers: dict[str, str]) -> None:
    _project, scene = _seed_nodes(client, auth_headers, 500)
    start = time.perf_counter()
    response = client.get(f"/api/v1/scenes/{scene['id']}/nodes", headers=auth_headers)
    elapsed = time.perf_counter() - start
    assert response.status_code == 200
    assert len(response.json()) == 501
    assert elapsed < 2.0, f"list nodes took {elapsed:.2f}s"


def test_export_large_scene_within_budget(client: TestClient, auth_headers: dict[str, str]) -> None:
    project, _scene = _seed_nodes(client, auth_headers, 300)
    start = time.perf_counter()
    response = client.post(
        f"/api/v1/projects/{project['id']}/exports",
        headers=auth_headers,
        json={"target": "html5"},
    )
    elapsed = time.perf_counter() - start
    assert response.status_code == 201
    export_id = response.json()["id"]

    job = {"status": "queued"}
    for _ in range(80):
        job = client.get(f"/api/v1/exports/{export_id}", headers=auth_headers).json()
        if job["status"] in TERMINAL:
            break
        time.sleep(0.05)
    assert job["status"] == "succeeded"
    assert elapsed < 10.0, f"export took {elapsed:.2f}s"
