import pytest
from httpx import AsyncClient

from tests.integration.test_rack import _create_room


@pytest.mark.asyncio
async def test_device_and_layout_flow(client: AsyncClient, auth_headers: dict[str, str]):
    room_id = await _create_room(client, auth_headers)

    models_resp = await client.get("/api/v1/device-models", headers=auth_headers)
    assert models_resp.status_code == 200
    model_id = models_resp.json()["data"]["items"][0]["id"]

    device_resp = await client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "hostname": "srv-001",
            "serial_number": "SN-001",
            "device_model_id": model_id,
        },
    )
    assert device_resp.status_code == 201
    device_id = device_resp.json()["data"]["id"]

    rack_resp = await client.post(
        "/api/v1/racks",
        headers=auth_headers,
        json={
            "room_id": room_id,
            "code": "RACK-DEV-001",
            "name": "Rack Dev",
            "total_u": 42,
        },
    )
    assert rack_resp.status_code == 201
    rack_id = rack_resp.json()["data"]["id"]

    mount_resp = await client.post(
        f"/api/v1/racks/{rack_id}/layout",
        headers=auth_headers,
        json={"device_id": device_id, "u_position": 10},
    )
    assert mount_resp.status_code == 200
    assert mount_resp.json()["data"]["valid"] is True

    device_get = await client.get(f"/api/v1/devices/{device_id}", headers=auth_headers)
    assert device_get.json()["data"]["rack_id"] == rack_id
    assert device_get.json()["data"]["u_position"] == 10

    svg_resp = await client.get(f"/api/v1/racks/{rack_id}/svg", headers=auth_headers)
    assert svg_resp.status_code == 200
    assert "<svg" in svg_resp.text

    summary_resp = await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()["data"]
    assert summary["device_count"] >= 1
    assert summary["mounted_device_count"] >= 1


@pytest.mark.asyncio
async def test_layout_conflict(client: AsyncClient, auth_headers: dict[str, str]):
    room_id = await _create_room(client, auth_headers)
    models = (await client.get("/api/v1/device-models", headers=auth_headers)).json()["data"]["items"]
    model_id = models[0]["id"]

    rack_id = (
        await client.post(
            "/api/v1/racks",
            headers=auth_headers,
            json={"room_id": room_id, "code": "RACK-CF", "name": "Rack CF", "total_u": 42},
        )
    ).json()["data"]["id"]

    d1 = (
        await client.post(
            "/api/v1/devices",
            headers=auth_headers,
            json={"hostname": "srv-a", "serial_number": "SN-A", "device_model_id": model_id},
        )
    ).json()["data"]["id"]
    d2 = (
        await client.post(
            "/api/v1/devices",
            headers=auth_headers,
            json={"hostname": "srv-b", "serial_number": "SN-B", "device_model_id": model_id},
        )
    ).json()["data"]["id"]

    await client.post(
        f"/api/v1/racks/{rack_id}/layout",
        headers=auth_headers,
        json={"device_id": d1, "u_position": 10},
    )
    conflict = await client.post(
        f"/api/v1/racks/{rack_id}/layout",
        headers=auth_headers,
        json={"device_id": d2, "u_position": 11},
    )
    assert conflict.status_code == 422
