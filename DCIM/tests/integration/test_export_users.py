import io

import pytest
from httpx import AsyncClient
from openpyxl import Workbook


def _build_import_xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["hostname", "serial_number", "model_code", "description"])
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_device_export_import(client: AsyncClient, auth_headers: dict[str, str]):
    models_resp = await client.get("/api/v1/device-models", headers=auth_headers)
    model_code = models_resp.json()["data"]["items"][0]["code"]

    import_bytes = _build_import_xlsx([
        ["import-srv-001", "IMP-SN-001", model_code, "Imported device"],
    ])
    import_resp = await client.post(
        "/api/v1/devices/import",
        headers=auth_headers,
        files={"file": ("devices.xlsx", import_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert import_resp.status_code == 200
    result = import_resp.json()["data"]
    assert result["created"] == 1
    assert result["failed"] == 0

    xlsx_resp = await client.get("/api/v1/devices/export?format=xlsx", headers=auth_headers)
    assert xlsx_resp.status_code == 200
    assert "spreadsheetml" in xlsx_resp.headers["content-type"]

    pdf_resp = await client.get("/api/v1/devices/export?format=pdf", headers=auth_headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF")

    template_resp = await client.get("/api/v1/devices/import/template", headers=auth_headers)
    assert template_resp.status_code == 200


@pytest.mark.asyncio
async def test_user_role_management(client: AsyncClient, auth_headers: dict[str, str]):
    perms_resp = await client.get("/api/v1/permissions", headers=auth_headers)
    assert perms_resp.status_code == 200
    permissions = perms_resp.json()["data"]
    assert any(p["code"] == "user:view" for p in permissions)

    role_resp = await client.post(
        "/api/v1/roles",
        headers=auth_headers,
        json={
            "code": "operator",
            "name": "Operator",
            "description": "Read-only operator",
            "permission_ids": [p["id"] for p in permissions if p["code"] in ("device:view", "rack:view")],
        },
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["data"]["id"]

    user_resp = await client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "username": "operator1",
            "email": "operator1@rackdcim.example.com",
            "password": "Operator@123456",
            "full_name": "Operator One",
            "role_ids": [role_id],
        },
    )
    assert user_resp.status_code == 201
    user_id = user_resp.json()["data"]["id"]
    assert user_resp.json()["data"]["roles"][0]["code"] == "operator"

    list_resp = await client.get("/api/v1/users", headers=auth_headers)
    assert list_resp.status_code == 200
    assert any(u["username"] == "operator1" for u in list_resp.json()["data"]["items"])

    update_resp = await client.put(
        f"/api/v1/users/{user_id}",
        headers=auth_headers,
        json={"full_name": "Operator Updated", "status": "inactive"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["full_name"] == "Operator Updated"

    delete_resp = await client.delete(f"/api/v1/users/{user_id}", headers=auth_headers)
    assert delete_resp.status_code == 200

    delete_role_resp = await client.delete(f"/api/v1/roles/{role_id}", headers=auth_headers)
    assert delete_role_resp.status_code == 200
