from fastapi.testclient import TestClient


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
)


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


def test_scene_node_properties_round_trip(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"name": "Scene Edit"},
    ).json()
    scene = client.get(f"/api/v1/projects/{project['id']}/scene", headers=auth_headers).json()

    node = client.post(
        f"/api/v1/projects/{project['id']}/scene/nodes",
        headers=auth_headers,
        json={
            "parent_id": scene["root_node_id"],
            "type": "image",
            "name": "Button",
            "transform": {"x": 24, "y": 18, "width": 72, "height": 26, "rotation": 0, "scale_x": 1, "scale_y": 1},
        },
    ).json()

    update = client.patch(
        f"/api/v1/scenes/{scene['id']}/nodes/{node['id']}",
        headers=auth_headers,
        json={
            "name": "Button Edited",
            "visible": False,
            "locked": True,
            "opacity": 0.4,
            "transform": {"x": 40, "y": 32, "width": 88, "height": 30, "rotation": 15, "scale_x": 1, "scale_y": 1},
        },
    )
    assert update.status_code == 200
    body = update.json()
    assert body["name"] == "Button Edited"
    assert body["visible"] is False
    assert body["locked"] is True
    assert body["opacity"] == 0.4
    assert body["transform"]["x"] == 40
    assert body["transform"]["rotation"] == 15


def test_scene_node_updates_require_a_fresh_version_when_supplied(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project = client.post("/api/v1/projects", headers=auth_headers, json={"name": "Node Versions"}).json()
    scene = client.get(f"/api/v1/projects/{project['id']}/scene", headers=auth_headers).json()
    node = client.post(
        f"/api/v1/projects/{project['id']}/scene/nodes",
        headers=auth_headers,
        json={"parent_id": scene["root_node_id"], "name": "Versioned Node"},
    )
    assert node.status_code == 201
    node_body = node.json()
    assert node_body["version"] == 1
    assert node.headers["etag"] == '"1"'

    updated = client.patch(
        f"/api/v1/scenes/{scene['id']}/nodes/{node_body['id']}",
        headers={**auth_headers, "If-Match": '"1"'},
        json={"name": "Fresh Node Update"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    stale = client.patch(
        f"/api/v1/scenes/{scene['id']}/nodes/{node_body['id']}",
        headers={**auth_headers, "If-Match": '"1"'},
        json={"name": "Stale Node Update"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_version"


def test_scene_node_parent_invariants_are_enforced(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"name": "Parent Invariants"},
    ).json()
    scene = client.get(f"/api/v1/projects/{project['id']}/scene", headers=auth_headers).json()
    create_url = f"/api/v1/projects/{project['id']}/scene/nodes"

    missing_parent = client.post(
        create_url,
        headers=auth_headers,
        json={"parent_id": "missing-parent", "name": "Invalid"},
    )
    assert missing_parent.status_code == 400
    assert missing_parent.json()["error"]["code"] == "invalid_parent"

    parent = client.post(create_url, headers=auth_headers, json={"name": "Parent"}).json()
    child = client.post(
        create_url,
        headers=auth_headers,
        json={"parent_id": parent["id"], "name": "Child"},
    ).json()

    self_parent = client.post(
        f"/api/v1/scenes/{scene['id']}/nodes/{parent['id']}/move",
        headers=auth_headers,
        json={"parent_id": parent["id"]},
    )
    assert self_parent.status_code == 400

    descendant_parent = client.post(
        f"/api/v1/scenes/{scene['id']}/nodes/{parent['id']}/move",
        headers=auth_headers,
        json={"parent_id": child["id"]},
    )
    assert descendant_parent.status_code == 400

    other_project = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"name": "Other Scene"},
    ).json()
    other_scene = client.get(
        f"/api/v1/projects/{other_project['id']}/scene",
        headers=auth_headers,
    ).json()
    cross_scene = client.post(
        f"/api/v1/scenes/{scene['id']}/nodes/{child['id']}/move",
        headers=auth_headers,
        json={"parent_id": other_scene["root_node_id"]},
    )
    assert cross_scene.status_code == 400


def test_scene_root_cannot_be_mutated_or_deleted(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"name": "Immutable Root"},
    ).json()
    scene = client.get(f"/api/v1/projects/{project['id']}/scene", headers=auth_headers).json()
    root_id = scene["root_node_id"]

    update = client.patch(
        f"/api/v1/scenes/{scene['id']}/nodes/{root_id}",
        headers=auth_headers,
        json={"name": "Changed Root"},
    )
    assert update.status_code == 409
    assert update.json()["error"]["code"] == "root_node_immutable"

    move = client.post(
        f"/api/v1/scenes/{scene['id']}/nodes/{root_id}/move",
        headers=auth_headers,
        json={"order_index": 10},
    )
    assert move.status_code == 409

    delete = client.delete(
        f"/api/v1/scenes/{scene['id']}/nodes/{root_id}",
        headers=auth_headers,
    )
    assert delete.status_code == 409

    root = client.get(
        f"/api/v1/scenes/{scene['id']}/nodes/{root_id}",
        headers=auth_headers,
    )
    assert root.status_code == 200
    assert root.json()["name"] == "Root"


def test_scene_node_names_must_not_be_blank(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"name": "Node Names"},
    ).json()
    scene = client.get(f"/api/v1/projects/{project['id']}/scene", headers=auth_headers).json()
    create_url = f"/api/v1/projects/{project['id']}/scene/nodes"

    create_response = client.post(create_url, headers=auth_headers, json={"name": "  "})
    assert create_response.status_code == 400

    node = client.post(create_url, headers=auth_headers, json={"name": "Valid"}).json()
    update_response = client.patch(
        f"/api/v1/scenes/{scene['id']}/nodes/{node['id']}",
        headers=auth_headers,
        json={"name": "\n"},
    )
    assert update_response.status_code == 400


def test_scene_node_can_reference_project_asset_and_metadata(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"name": "Asset Placement API"},
    ).json()
    scene = client.get(f"/api/v1/projects/{project['id']}/scene", headers=auth_headers).json()
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        headers=auth_headers,
        files={"file": ("button.png", PNG_BYTES, "image/png")},
    ).json()

    node = client.post(
        f"/api/v1/projects/{project['id']}/scene/nodes",
        headers=auth_headers,
        json={
            "type": "image",
            "name": "Placed Button",
            "asset_id": asset["id"],
            "text_properties": {"alt": "Button"},
            "style_properties": {"fit": "contain"},
            "effect_metadata": {"source": "user"},
        },
    )
    assert node.status_code == 201
    body = node.json()
    assert body["asset_id"] == asset["id"]
    assert body["text_properties"] == {"alt": "Button"}
    assert body["style_properties"] == {"fit": "contain"}
    assert body["effect_metadata"] == {"source": "user"}

    update = client.patch(
        f"/api/v1/scenes/{scene['id']}/nodes/{body['id']}",
        headers=auth_headers,
        json={"asset_id": asset["id"]},
    )
    assert update.status_code == 200

    missing_asset = client.post(
        f"/api/v1/projects/{project['id']}/scene/nodes",
        headers=auth_headers,
        json={"type": "image", "asset_id": "missing-asset"},
    )
    assert missing_asset.status_code == 404
