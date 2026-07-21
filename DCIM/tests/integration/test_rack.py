import pytest
from httpx import AsyncClient


async def _create_room(client: AsyncClient, headers: dict[str, str]) -> str:
    dc_resp = await client.post(
        "/api/v1/datacenters",
        headers=headers,
        json={"code": "DC-RACK", "name": "Rack DC", "location": "Beijing"},
    )
    dc_id = dc_resp.json()["data"]["id"]

    building_resp = await client.post(
        "/api/v1/buildings",
        headers=headers,
        json={"datacenter_id": dc_id, "name": "Building A"},
    )
    building_id = building_resp.json()["data"]["id"]

    floor_resp = await client.post(
        "/api/v1/floors",
        headers=headers,
        json={"building_id": building_id, "name": "Floor 1"},
    )
    floor_id = floor_resp.json()["data"]["id"]

    room_resp = await client.post(
        "/api/v1/rooms",
        headers=headers,
        json={"floor_id": floor_id, "name": "Room 101"},
    )
    return room_resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_rack_crud(client: AsyncClient, auth_headers: dict[str, str]):
    room_id = await _create_room(client, auth_headers)

    create_resp = await client.post(
        "/api/v1/racks",
        headers=auth_headers,
        json={
            "room_id": room_id,
            "code": "RACK-001",
            "name": "Rack A01",
            "total_u": 42,
            "row_no": 1,
            "column_no": 1,
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()["data"]
    assert created["code"] == "RACK-001"
    assert created["total_u"] == 42
    assert created["free_u"] == 42
    assert created["utilization"] == 0.0

    rack_id = created["id"]
    layout_resp = await client.get(f"/api/v1/racks/{rack_id}/layout", headers=auth_headers)
    assert layout_resp.status_code == 200
    positions = layout_resp.json()["data"]["positions"]
    assert len(positions) == 42
    assert positions[0]["u_position"] == 1

    list_resp = await client.get("/api/v1/racks", headers=auth_headers, params={"room_id": room_id})
    assert list_resp.status_code == 200
    assert list_resp.json()["data"]["pagination"]["total"] >= 1

    delete_resp = await client.delete(f"/api/v1/racks/{rack_id}", headers=auth_headers)
    assert delete_resp.status_code == 200


@pytest.mark.asyncio
async def test_rack_requires_permission(client: AsyncClient):
    response = await client.get("/api/v1/racks")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rack_template_list(client: AsyncClient, auth_headers: dict[str, str]):
    response = await client.get("/api/v1/rack-templates", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["pagination"]["total"] >= 2
