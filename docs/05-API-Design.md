---
title: API Design Specification
project: RackDCIM Pro
version: 1.4.0
status: Active
author: Enzo
date: 2026-07-22
last_code_sync: 2026-07-22
category: API
specification: OpenAPI 3.x
---

# API Design Specification

> RESTful API — Base URL `/api/v1` — OpenAPI at `/api/v1/docs`

---

## Revision History

| Version | Date | Author | Description |
| ------- | ---- | ------ | ----------- |
| 1.3.0 | 2026-07-22 | Enzo | Complete endpoint catalog (~95 routes), schemas, error codes |
| 1.4.0 | 2026-07-22 | Enzo | POST/PUT JSON examples; Postman Collection sync |

---

## 1. API Overview

| Property | Value |
| -------- | ----- |
| Base path | `/api/v1` |
| Protocol | HTTP(S); dev HTTP |
| Format | JSON UTF-8 |
| Auth | JWT Bearer (except public routes) |
| OpenAPI | `/api/v1/openapi.json` |
| Swagger UI | `/api/v1/docs` |
| ReDoc | `/api/v1/redoc` |
| Root health | `GET /health` (outside prefix) |

---

## 2. Request Conventions

### 2.1 Headers

```http
Content-Type: application/json
Accept: application/json
Authorization: Bearer <access_token>
```

Multipart (import endpoints):

```http
Content-Type: multipart/form-data
Authorization: Bearer <access_token>
```

### 2.2 Pagination Query

| Param | Type | Default | Max |
| ----- | ---- | ------- | --- |
| page | int | 1 | — |
| page_size | int | 20 | 500 |
| keyword | string? | — | search |
| sort | string | created_at | field name |
| order | string | desc | asc \| desc |

Schema: `PaginationParams` in `app/schemas/common.py`.

---

## 3. Response Envelope

### 3.1 Success (single object)

```json
{
  "code": 0,
  "message": "success",
  "data": { },
  "timestamp": "2026-07-22T10:00:00"
}
```

### 3.2 Success (paginated)

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 105,
      "pages": 6
    }
  },
  "timestamp": "2026-07-22T10:00:00"
}
```

### 3.3 Error

```json
{
  "code": 10004,
  "message": "U Position Occupied",
  "details": {},
  "timestamp": "2026-07-22T10:00:00"
}
```

HTTP status derived in `core/handlers.py`:

| Business Code | HTTP | Meaning |
| ------------- | ---- | ------- |
| 0 | 200 | Success |
| 401 | 401 | Unauthorized |
| 403 | 403 | Forbidden |
| 404 | 404 | Not found |
| 422 | 422 | Validation (Pydantic or 10004/10005) |
| 10001 | 404 | Resource not found |
| 10002 | 409 | Conflict (rack slot, position) |
| 10003 | 409 | Device/contract duplicate or not found |
| 10004 | 422 | Business validation |
| 10005 | 422 | Import failed |
| 500 | 500 | Internal error |

---

## 4. Authentication

### 4.1 Login

```http
POST /api/v1/auth/login
```

Request:

```json
{
  "username": "admin",
  "password": "Admin@12345678"
}
```

Response `data`:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer"
}
```

### 4.2 Refresh

```http
POST /api/v1/auth/refresh
```

Body: `{ "refresh_token": "..." }`

### 4.3 Profile

```http
GET /api/v1/auth/profile
```

Returns user + roles + permission codes.

### 4.4 Logout

```http
POST /api/v1/auth/logout
```

---

## 5. Permission Matrix

| Permission | Scope |
| ---------- | ----- |
| admin:* | All (short-circuit) |
| datacenter:view\|create\|update\|delete | DC, Room |
| rack:view\|create\|update\|delete | Racks, templates |
| device:view\|create\|update\|delete | Devices, IP, contracts, layout mount |
| device:import | Excel import |
| device:export | Excel/PDF export |
| dashboard:view | Dashboard |
| audit:view | Audit logs |
| user:view\|create\|update\|delete | Users |
| role:view\|create\|update\|delete | Roles, GET permissions |

Mount/unmount requires `device:update`. Rack layout POST requires `device:update`.

---

## 6. Endpoint Catalog

> **Legend:** ✅ Implemented · 📋 Planned

### 6.1 Health ✅

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/health` | No | App root health |
| GET | `/api/v1/health` | No | API health |

### 6.2 Auth ✅

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/auth/login` | Issue tokens |
| POST | `/auth/refresh` | Refresh access token |
| GET | `/auth/profile` | Current user + permissions |
| POST | `/auth/logout` | Logout |

### 6.3 Dashboard ✅

| Method | Path | Permission | Description |
| ------ | ---- | ---------- | ----------- |
| GET | `/dashboard/summary` | dashboard:view | Counts: DC, rooms, racks, devices, U stats |
| GET | `/dashboard/utilization` | dashboard:view | Rack utilization breakdown |
| GET | `/dashboard/power` | — | 📋 Not implemented |
| GET | `/dashboard/device-count` | — | 📋 Not implemented |

### 6.4 Infrastructure ✅

**Datacenters** — `datacenter:*`

| Method | Path |
| ------ | ---- |
| GET | `/datacenters` |
| GET | `/datacenters/{id}` |
| POST | `/datacenters` |
| PUT | `/datacenters/{id}` |
| DELETE | `/datacenters/{id}` |

**Buildings / Floors** — `datacenter:*`

| Method | Path |
| ------ | ---- |
| GET/POST | `/buildings` |
| PUT/DELETE | `/buildings/{id}` |
| GET/POST | `/floors` |
| PUT/DELETE | `/floors/{id}` |

**Rooms** — `datacenter:*`

| Method | Path | Notes |
| ------ | ---- | ----- |
| GET | `/rooms` | Paginated list |
| POST | `/rooms` | Standard create |
| POST | `/rooms/quick` | **Primary UI path** — auto building/floor |
| PUT | `/rooms/{id}` | Update layout/codes |
| DELETE | `/rooms/{id}` | Soft delete |

**POST /rooms/quick** key fields:

| Field | Required | Description |
| ----- | -------- | ----------- |
| datacenter_id | ✓ | Existing DC |
| building_no | ✓ | Creates building if missing |
| room_no | ✓ | Stored as room.name |
| layout_mode | | auto (default) \| manual |
| rack_rows, rack_columns | | auto grid |
| row_layout | | manual per-row counts |
| code_mode | | auto \| custom |
| code_prefix | | Default `A` |
| slot_codes | | Required when custom |

### 6.5 Rack ✅

**Templates** — `rack:*`

| Method | Path |
| ------ | ---- |
| GET/POST | `/rack-templates` |
| POST | `/rack-templates/{id}/apply-to-room` |
| POST | `/rack-templates/{id}/unapply-from-room` |
| PUT/DELETE | `/rack-templates/{id}` |

**Racks** — `rack:*` (layout: `device:update`)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/racks` | List/filter by room |
| GET | `/racks/code-check` | Validate code availability |
| POST | `/racks/place-batch` | Batch place by mode |
| POST | `/racks/batch-delete` | Batch soft delete |
| GET | `/racks/{id}` | Detail |
| GET | `/racks/{id}/layout` | U-position layout |
| GET | `/racks/{id}/svg` | SVG string |
| POST | `/racks/{id}/layout` | Update rack layout |
| POST/PUT/DELETE | `/racks`, `/racks/{id}` | CRUD |

### 6.6 Device & Catalog ✅

**Devices** — `device:*`

| Method | Path | Permission |
| ------ | ---- | ---------- |
| GET/POST | `/devices` | device:view/create |
| GET/PUT/DELETE | `/devices/{id}` | device:view/update/delete |
| POST | `/devices/batch-delete` | device:delete |
| GET | `/devices/export?format=xlsx\|pdf` | device:export |
| GET | `/devices/import/template` | device:import |
| POST | `/devices/import` | device:import (multipart) |

**Catalog** (same device permissions):

| Resource | Paths |
| -------- | ----- |
| Device types | `/device-types`, `/device-types/{id}` |
| Param profiles | `/device-param-profiles`, `.../{id}` |
| System profiles | `/device-system-profiles`, `.../{id}` |
| BMC profiles | `/device-bmc-profiles`, `.../{id}` |
| Manufacturers | GET/POST `/manufacturers` |
| Models | `/device-models`, `/device-models/{id}` |

Import response:

```json
{
  "created": 10,
  "failed": 2,
  "errors": [{ "row": 3, "message": "..." }]
}
```

### 6.7 Device Contracts ✅

Prefix: `/device-contracts` — `device:*`

| Method | Path |
| ------ | ---- |
| GET | `/device-contracts` |
| GET | `/device-contracts/summary` |
| GET | `/device-contracts/{id}` |
| POST | `/device-contracts` |
| PUT | `/device-contracts/{id}` |
| DELETE | `/device-contracts/{id}` |
| POST | `/device-contracts/{id}/bind-devices` |
| POST | `/device-contracts/{id}/unbind-devices` |
| GET | `/device-contracts/items/import/template` |
| POST | `/device-contracts/items/import` |

### 6.8 IP Addresses ✅

Prefix: `/ip-addresses` — `device:*`

| Method | Path |
| ------ | ---- |
| GET/POST | `/ip-addresses` |
| PUT | `/ip-addresses/{id}` |
| DELETE | `/ip-addresses/{id}` |
| POST | `/ip-addresses/{id}/bind` |
| POST | `/ip-addresses/batch-create` |
| POST | `/ip-addresses/batch-delete` |
| POST | `/ip-addresses/batch-bind` |
| POST | `/ip-addresses/allocate` |
| POST | `/ip-addresses/batch-status` |

Bind types: `none`, `device`, `rack`, `rack_range`. Status: `free`, `allocated`, `disabled`.

### 6.9 Layout Engine ✅

Prefix: `/layout` — mount ops need `device:update`

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/layout/validate` | Check U assignment |
| POST | `/layout/auto` | Auto-assign U positions |
| POST | `/layout/mount` | Mount device to rack |
| POST | `/layout/unmount` | Unmount device |
| POST | `/layout/batch-mount` | Batch mount |
| POST | `/layout/batch-unmount` | Batch unmount |
| GET | `/layout/result` | 📋 Planned |

### 6.10 SVG & Audit ✅ / 📋

| Method | Path | Permission | Status |
| ------ | ---- | ---------- | ------ |
| GET | `/racks/{id}/svg` | rack:view | ✅ |
| GET | `/svg/rack/{rack_id}` | rack:view | ✅ alias |
| GET | `/audit/logs` | audit:view | ✅ |
| GET | `/svg/export` | — | 📋 |
| POST | `/svg/render` | — | 📋 |

### 6.11 Users & Roles ✅

| Method | Path | Permission |
| ------ | ---- | ---------- |
| GET/POST | `/users` | user:view/create |
| GET/PUT/DELETE | `/users/{id}` | user:view/update/delete |
| GET/POST | `/roles` | role:view/create |
| PUT/DELETE | `/roles/{id}` | role:view/update/delete |
| GET | `/permissions` | role:view |

Rules: cannot delete user `admin`; cannot delete/modify permissions of role `admin`.

### 6.12 File Service 📋

| Method | Path | Status |
| ------ | ---- | ------ |
| POST | `/files/upload` | 📋 |
| GET | `/files/{id}` | 📋 |
| DELETE | `/files/{id}` | 📋 |

---

## 7. OpenAPI & SDK

- Auto-generated from FastAPI route decorators + Pydantic models
- Frontend types manually maintained in `frontend/src/types/api.ts`
- Future: openapi-generator for TS client

---

## 8. Rate Limiting 📋

| Endpoint Class | Planned Limit |
| -------------- | ------------- |
| General API | 100 req/min |
| Login | 10 req/min |
| Import | 5 req/min |

Not enforced in V1 codebase.

---

## 10. POST / PUT Request & Response Examples

> Schema 源文件：`backend/app/schemas/`。以下示例省略 `timestamp` 等元字段，聚焦 `data` 载荷。  
> UUID 示例值请替换为实际 ID（可从列表接口 GET 获取）。

### 10.1 Auth

#### POST /auth/login

Request:

```json
{
  "username": "admin",
  "password": "Admin@12345678"
}
```

Response `data`:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

#### POST /auth/refresh

Request:

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

Response `data`: 同 login，返回新的 token 对。

#### POST /auth/logout

Request: `{}` 或空 body。

Response `data`:

```json
{
  "message": "logged out"
}
```

---

### 10.2 Infrastructure

#### POST /datacenters

Request:

```json
{
  "code": "DC-SH-01",
  "name": "上海数据中心",
  "location": "上海市浦东新区",
  "description": "主数据中心"
}
```

Response `data`:

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "code": "DC-SH-01",
  "name": "上海数据中心",
  "location": "上海市浦东新区",
  "description": "主数据中心",
  "created_at": "2026-07-22T10:00:00",
  "updated_at": "2026-07-22T10:00:00"
}
```

#### PUT /datacenters/{id}

Request（部分更新）:

```json
{
  "location": "上海市浦东新区张江",
  "description": "更新描述"
}
```

#### POST /buildings

Request:

```json
{
  "datacenter_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "A栋",
  "description": null
}
```

#### POST /floors

Request:

```json
{
  "building_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "name": "1F"
}
```

#### POST /rooms/quick

Request（自动布局 + 自动编号，前端主路径）:

```json
{
  "datacenter_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "building_no": "A",
  "room_no": "101",
  "layout_mode": "auto",
  "rack_rows": 3,
  "rack_columns": 6,
  "code_mode": "auto",
  "code_prefix": "A",
  "description": "主机房"
}
```

Response `data`（节选）:

```json
{
  "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "floor_id": "...",
  "name": "101",
  "datacenter_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "datacenter_name": "上海数据中心",
  "building_no": "A",
  "room_no": "101",
  "layout_mode": "auto",
  "rack_rows": 3,
  "rack_columns": 6,
  "row_layout": [6, 6, 6],
  "rack_capacity": 18,
  "code_mode": "auto",
  "code_prefix": "A",
  "slot_codes": [
    ["A01", "A02", "A03", "A04", "A05", "A06"],
    ["B01", "B02", "B03", "B04", "B05", "B06"],
    ["C01", "C02", "C03", "C04", "C05", "C06"]
  ]
}
```

#### PUT /rooms/{id}

Request（手动调整布局，需谨慎）:

```json
{
  "room_no": "101",
  "layout_mode": "manual",
  "row_layout": [6, 6, 8],
  "code_mode": "auto",
  "code_prefix": "A-D"
}
```

---

### 10.3 Rack

#### POST /rack-templates

Request:

```json
{
  "code": "STD-42U",
  "name": "Standard 42U",
  "total_u": 42,
  "width": 600,
  "depth": 1000,
  "description": "标准 42U 机柜"
}
```

#### POST /rack-templates/{id}/apply-to-room

Request:

```json
{
  "room_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "fill_empty_slots": true
}
```

Response `data`:

```json
{
  "updated": 0,
  "created": 18,
  "skipped": 0,
  "errors": []
}
```

#### POST /racks/place-batch

Request（整机房套用模板）:

```json
{
  "room_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "mode": "all",
  "template_id": "d4e5f6a7-b8c9-0123-def0-234567890123",
  "fill_empty_slots": true,
  "update_existing": true
}
```

#### POST /racks

Request:

```json
{
  "room_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "code": "A01",
  "name": "A01",
  "rack_template_id": "d4e5f6a7-b8c9-0123-def0-234567890123",
  "row_no": 1,
  "column_no": 1,
  "total_u": 42,
  "status": "active"
}
```

#### PUT /racks/{id}

Request:

```json
{
  "name": "A01-GPU",
  "status": "maintenance",
  "description": "维护中"
}
```

#### POST /racks/{id}/layout

Request（单机柜上架，等同 mount）:

```json
{
  "device_id": "e5f6a7b8-c9d0-1234-ef01-345678901234",
  "u_position": 10
}
```

Response `data`:

```json
{
  "valid": true,
  "message": "Device mounted successfully",
  "occupied_positions": [10, 11]
}
```

#### POST /racks/batch-delete

Request:

```json
{
  "ids": ["rack-id-1", "rack-id-2"]
}
```

---

### 10.4 Device & Catalog

#### POST /devices

Request:

```json
{
  "hostname": "srv-gpu-001",
  "serial_number": "SN-GPU-001",
  "device_model_id": "f6a7b8c9-d0e1-2345-f012-456789012345",
  "device_type_id": "compute-type-id",
  "height_u": 2,
  "power": 750.0,
  "description": "GPU 服务器"
}
```

Response `data`（节选）:

```json
{
  "id": "e5f6a7b8-c9d0-1234-ef01-345678901234",
  "hostname": "srv-gpu-001",
  "serial_number": "SN-GPU-001",
  "status": "stock",
  "rack_id": null,
  "u_position": null,
  "height_u": 2
}
```

#### PUT /devices/{id}

Request:

```json
{
  "hostname": "srv-gpu-001-new",
  "power": 800.0,
  "contract_id": "contract-uuid"
}
```

#### POST /devices/batch-delete

Request:

```json
{
  "ids": ["device-id-1", "device-id-2"]
}
```

#### POST /devices/import

Request: `multipart/form-data`，字段 `file` = Excel 文件（非 JSON）。

Response `data`:

```json
{
  "created": 10,
  "failed": 1,
  "errors": ["Row 5: model_code UNKNOWN not found"]
}
```

#### POST /device-types

Request:

```json
{
  "code": "gpu",
  "name": "GPU 服务器",
  "description": "计算节点"
}
```

#### PUT /device-param-profiles/{id}

Request:

```json
{
  "name": "R750 标准配置",
  "payload": {
    "cpu": { "cores": 32, "architecture": "c86" },
    "memory": { "size_gb": 256, "ddr_type": "DDR5" },
    "disks": [{ "size_gb": 960, "count": 2, "media_type": "ssd" }]
  }
}
```

#### POST /manufacturers

Request:

```json
{
  "code": "DELL",
  "name": "Dell Technologies"
}
```

#### POST /device-models

Request:

```json
{
  "code": "R750-2U",
  "name": "PowerEdge R750",
  "manufacturer_id": "mfg-dell-id",
  "height_u": 2,
  "power": 750,
  "weight": 25.0
}
```

---

### 10.5 Device Contract

#### POST /device-contracts

Request:

```json
{
  "contract_no": "PO-2026-001",
  "project_no": "PRJ-GPU-01",
  "device_items": [
    {
      "device_name": "GPU 服务器",
      "device_model_name": "PowerEdge R750",
      "manufacturer_name": "Dell",
      "quantity": 10,
      "quantity_unit": "台",
      "unit_price": 85000.00,
      "price_unit": "yuan"
    }
  ],
  "purchase_date": "2026-06-01",
  "description": "2026 年 GPU 采购"
}
```

Response `data`（节选）:

```json
{
  "id": "contract-uuid",
  "contract_no": "PO-2026-001",
  "quantity": 10,
  "contract_total": 850000.00,
  "linked_count": 0,
  "device_items": [ "..." ]
}
```

#### PUT /device-contracts/{id}

Request:

```json
{
  "description": "已验收",
  "contract_total": 840000.00
}
```

#### POST /device-contracts/{id}/bind-devices

Request:

```json
{
  "device_ids": [
    "e5f6a7b8-c9d0-1234-ef01-345678901234"
  ]
}
```

Response `data`:

```json
{
  "bound": 1,
  "skipped": 0,
  "errors": []
}
```

#### POST /device-contracts/items/import

Request: `multipart/form-data`，字段 `file` = Excel。

Response `data`:

```json
{
  "items": [ { "device_name": "...", "device_model_name": "...", "quantity": 5 } ],
  "imported": 5,
  "skipped": 0,
  "errors": []
}
```

---

### 10.6 IP Address

#### POST /ip-addresses

Request:

```json
{
  "system_ip": "10.0.1.100",
  "bmc_ip": "10.0.2.100",
  "vip": null,
  "netmask": "255.255.255.0",
  "gateway": "10.0.1.1",
  "dns": "8.8.8.8",
  "label": "GPU-001",
  "status": "free"
}
```

#### PUT /ip-addresses/{id}

Request:

```json
{
  "label": "GPU-001-prod",
  "status": "disabled"
}
```

#### POST /ip-addresses/batch-create

Request:

```json
{
  "start_system_ip": "10.0.1.1",
  "end_system_ip": "10.0.1.50",
  "start_bmc_ip": "10.0.2.1",
  "netmask": "255.255.255.0",
  "gateway": "10.0.1.1",
  "label_prefix": "AUTO"
}
```

Response `data`:

```json
{
  "created": 50,
  "skipped": 0,
  "errors": []
}
```

#### POST /ip-addresses/{id}/bind

Request（绑定设备）:

```json
{
  "bind_type": "device",
  "device_id": "e5f6a7b8-c9d0-1234-ef01-345678901234"
}
```

Request（绑定机柜范围）:

```json
{
  "bind_type": "rack_range",
  "room_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "rack_ids": ["rack-1", "rack-2"]
}
```

#### POST /ip-addresses/allocate

Request:

```json
{
  "ip_ids": ["ip-1", "ip-2", "ip-3"],
  "room_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "rack_ids": [],
  "row_nos": [1, 2],
  "column_nos": []
}
```

Response `data`（节选）:

```json
{
  "allocated": 3,
  "skipped": 0,
  "errors": [],
  "assignments": [
    {
      "ip_id": "ip-1",
      "system_ip": "10.0.1.1",
      "device_id": "...",
      "rack_code": "A01",
      "u_position": 10
    }
  ]
}
```

#### POST /ip-addresses/batch-status

Request:

```json
{
  "ids": ["ip-1", "ip-2"],
  "status": "disabled"
}
```

---

### 10.7 Layout

#### POST /layout/validate

Request:

```json
{
  "rack_id": "rack-uuid",
  "u_position": 10,
  "height_u": 2,
  "exclude_device_id": null
}
```

Response `data`:

```json
{
  "valid": true,
  "message": "OK",
  "occupied_positions": []
}
```

Error example `data`:

```json
{
  "valid": false,
  "message": "U position conflict",
  "occupied_positions": [10, 11]
}
```

#### POST /layout/auto

Request:

```json
{
  "rack_id": "rack-uuid",
  "device_id": "device-uuid"
}
```

Response `data`:

```json
{
  "u_position": 10,
  "message": "Auto-assigned U10"
}
```

#### POST /layout/mount

Request:

```json
{
  "device_id": "device-uuid",
  "rack_id": "rack-uuid",
  "u_position": 10
}
```

#### POST /layout/unmount

Request:

```json
{
  "device_id": "device-uuid"
}
```

#### POST /layout/batch-mount

Request:

```json
{
  "room_id": "room-uuid",
  "device_ids": ["device-1", "device-2"],
  "new_devices": [],
  "rack_ids": [],
  "row_nos": [1],
  "column_nos": [],
  "per_rack_count": 2,
  "start_u": 1,
  "gap_u": 1,
  "ip_ids": ["ip-1", "ip-2"]
}
```

Response `data`:

```json
{
  "mounted": 2,
  "created": 0,
  "ip_bound": 2,
  "skipped": 0,
  "errors": [],
  "assignments": []
}
```

#### POST /layout/batch-unmount

Request:

```json
{
  "device_ids": ["device-1", "device-2"]
}
```

---

### 10.8 Users & Roles

#### POST /users

Request:

```json
{
  "username": "operator1",
  "email": "operator1@example.com",
  "password": "SecurePass@1234",
  "full_name": "运维操作员",
  "role_ids": ["role-operator-uuid"],
  "status": "active"
}
```

#### PUT /users/{id}

Request:

```json
{
  "full_name": "高级运维",
  "role_ids": ["role-a", "role-b"],
  "status": "active"
}
```

#### POST /roles

Request:

```json
{
  "code": "operator",
  "name": "运维人员",
  "description": "日常运维",
  "permission_ids": [
    "perm-datacenter-view",
    "perm-device-view",
    "perm-device-update"
  ]
}
```

#### PUT /roles/{id}

Request:

```json
{
  "name": "运维人员（扩展）",
  "permission_ids": ["perm-id-1", "perm-id-2"]
}
```

> 不可对 `code=admin` 的角色提交空 `permission_ids` 或删除该角色。

---

### 10.9 Error Response Examples

Validation (422):

```json
{
  "code": 422,
  "message": "Validation failed",
  "details": {
    "errors": [
      {
        "loc": ["body", "password"],
        "msg": "String should have at least 12 characters",
        "type": "string_too_short"
      }
    ]
  }
}
```

Business conflict (409, code 10002):

```json
{
  "code": 10002,
  "message": "Rack position already occupied",
  "details": {}
}
```

Not found (404, code 10001):

```json
{
  "code": 10001,
  "message": "Rack not found",
  "details": {}
}
```

---

## 11. Postman Collection

与 OpenAPI 同步的 Postman Collection 位于：

```text
docs/postman/RackDCIM-Pro.postman_collection.json
docs/postman/RackDCIM-Pro.postman_environment.json
docs/postman/README.md
```

### 11.1 导入步骤

1. 启动后端：`uvicorn app.main:app --reload --port 8000`
2. Postman → **Import** → 选择上述两个 JSON 文件
3. 右上角 Environment 选择 **RackDCIM Pro - Local**
4. 运行 **Auth → Login** 请求（自动写入 `access_token`）
5. 其余请求继承 Collection Bearer `{{access_token}}`

### 11.2 环境变量

| Variable | Default | Description |
| -------- | ------- | ----------- |
| base_url | http://localhost:8000/api/v1 | API 根路径 |
| access_token | (empty) | Login 后自动填充 |
| refresh_token | (empty) | Login 后自动填充 |
| datacenter_id | (empty) | 手动或脚本填充 |
| room_id | (empty) | 手动或脚本填充 |
| rack_id | (empty) | 手动或脚本填充 |
| device_id | (empty) | 手动或脚本填充 |

### 11.3 与 OpenAPI 同步

| 方式 | 说明 |
| ---- | ---- |
| 手动 | 修改 API 后更新 Collection JSON + 本文档 §10 |
| 自动（推荐） | Postman → Import → Link `http://localhost:8000/api/v1/openapi.json` |
| 校验 | 对比 `/api/v1/openapi.json` paths 与 Collection item 数量 |

OpenAPI 为权威来源；Collection 为便捷测试套件。

---

## 12. API Lifecycle

| Status | Meaning |
| ------ | ------- |
| Stable | V1 implemented endpoints |
| Draft | Designed, not coded |
| Deprecated | Scheduled removal |
| Removed | No longer available |

---

## Appendix A — Resource URI Summary

| Resource | Base URI |
| -------- | -------- |
| Auth | /auth |
| Dashboard | /dashboard |
| DataCenter | /datacenters |
| Room | /rooms |
| Rack | /racks |
| Rack Template | /rack-templates |
| Device | /devices |
| Contract | /device-contracts |
| IP | /ip-addresses |
| Layout | /layout |
| Users | /users |
| Roles | /roles |
| Audit | /audit/logs |

---

## References

- [07-Backend-Design.md](07-Backend-Design.md)
- [11-Security.md](11-Security.md)
- [postman/README.md](postman/README.md)
- Live spec: http://localhost:8000/api/v1/docs
- OpenAPI JSON: http://localhost:8000/api/v1/openapi.json
