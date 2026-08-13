from fastapi.testclient import TestClient


def test_created_project_has_root_scene_and_node(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project = client.post("/api/v1/projects", headers=auth_headers, json={"name": "Scene Test"}).json()
    scene = client.get(f"/api/v1/projects/{project['id']}/scene", headers=auth_headers)
    assert scene.status_code == 200
    body = scene.json()
    assert body["width"] == 1920
    assert body["height"] == 1080

    nodes = client.get(f"/api/v1/scenes/{body['id']}/nodes", headers=auth_headers)
    assert nodes.status_code == 200
    assert any(node["type"] == "root" for node in nodes.json())

