import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin@12345678"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["access_token"]
    assert body["data"]["refresh_token"]


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_profile(client: AsyncClient, auth_headers: dict[str, str]):
    response = await client.get("/api/v1/auth/profile", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["username"] == "admin"
    assert "admin:*" in body["data"]["permissions"]


@pytest.mark.asyncio
async def test_datacenter_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/datacenters")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_datacenter_crud(client: AsyncClient, auth_headers: dict[str, str]):
    create_resp = await client.post(
        "/api/v1/datacenters",
        headers=auth_headers,
        json={
            "code": "DC-001",
            "name": "Primary Data Center",
            "location": "Shanghai",
            "description": "Main facility",
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()["data"]
    assert created["code"] == "DC-001"

    list_resp = await client.get("/api/v1/datacenters", headers=auth_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]["items"]
    assert len(items) >= 1

    dc_id = created["id"]
    update_resp = await client.put(
        f"/api/v1/datacenters/{dc_id}",
        headers=auth_headers,
        json={"name": "Primary DC Updated"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["name"] == "Primary DC Updated"

    delete_resp = await client.delete(f"/api/v1/datacenters/{dc_id}", headers=auth_headers)
    assert delete_resp.status_code == 200
