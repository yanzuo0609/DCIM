---
title: API Design Specification
project: RackDCIM Pro
version: 1.0.0
status: Draft
author: Enzo
date: 2026-07-16
category: API
specification: OpenAPI 3.1
---

# API Design Specification

> RackDCIM Pro
>
> RESTful API Design Specification

---

# Revision History

| Version | Date       | Author | Description     |
| ------- | ---------- | ------ | --------------- |
| 1.0.0   | 2026-07-16 | Enzo   | Initial Version |
| 1.1.0   | 2026-07-17 | Enzo   | Sync V1: rooms/quick, import/export, users/roles |

---

# Table of Contents

1. API Overview
2. API Design Principles
3. API Version Strategy
4. Authentication
5. Request Specification
6. Response Specification
7. Error Codes
8. Pagination
9. Filtering & Sorting
10. API Modules
11. OpenAPI Convention
12. Security
13. Rate Limiting
14. API Lifecycle

---

# 1 API Overview

RackDCIM Pro 所有接口均采用 RESTful 风格。

协议：

```
HTTPS
```

数据格式：

```
JSON
```

字符集：

```
UTF-8
```

API Base URL

```
/api/v1
```

未来版本：

```
/api/v2
```

---

# 2 API Design Principles

遵循：

- RESTful
- OpenAPI 3.1
- Stateless
- Resource Oriented
- Versioned API

原则：

- 一个URL对应一个资源
- 使用HTTP Method表示行为
- 无Session
- Token认证
- 所有接口统一返回格式

---

# 3 API Version Strategy

统一采用URI版本控制：

```
/api/v1
/api/v2
```

禁止：

```
?action=add
?action=delete
```

---

# 4 Authentication

认证方式：

```
JWT Bearer Token
```

Header：

```http
Authorization: Bearer <token>
```

登录流程：

```
Login

↓

Verify Password

↓

Generate JWT

↓

Return Token

↓

Access API
```

Token：

```
Access Token

Refresh Token
```

---

# 5 Request Specification

## Headers

```http
Content-Type: application/json
Accept: application/json
Authorization: Bearer Token
```

---

## Request Body

统一：

```json
{
    "name":"Rack001",
    "description":"Demo"
}
```

---

## Query

分页：

```
?page=1

&page_size=20
```

排序：

```
?sort=name

?order=asc
```

过滤：

```
?status=active

?keyword=GPU
```

---

# 6 Response Specification

统一格式：

```json
{
    "code":0,
    "message":"success",
    "data":{},
    "timestamp":"2026-07-16T10:00:00Z"
}
```

分页：

```json
{
    "code":0,
    "data":[...],
    "pagination":{
        "page":1,
        "page_size":20,
        "total":105,
        "pages":6
    }
}
```

---

# 7 Error Codes

| Code | Description           |
| ---- | --------------------- |
| 0    | Success               |
| 400  | Bad Request           |
| 401  | Unauthorized          |
| 403  | Forbidden             |
| 404  | Not Found             |
| 409  | Conflict              |
| 422  | Validation Failed     |
| 429  | Too Many Requests     |
| 500  | Internal Server Error |

业务错误：

| Code  | Meaning             |
| ----- | ------------------- |
| 10001 | Rack Not Found      |
| 10002 | Rack Conflict       |
| 10003 | Device Exists       |
| 10004 | U Position Occupied |
| 10005 | Import Failed       |

---

# 8 Pagination

统一：

```http
GET /devices?page=1&page_size=20
```

返回：

```json
{
  "items":[],
  "pagination":{
      "page":1,
      "page_size":20,
      "total":200,
      "pages":10
  }
}
```

---

# 9 Filtering & Sorting

支持：

```
keyword

status

room

rack

manufacturer

device_type
```

排序：

```
name

created_at

updated_at
```

支持多字段排序。

---

# 10 API Modules

## Authentication

```
POST /auth/login

POST /auth/logout

POST /auth/refresh

GET /auth/profile
```

---

## User

```
GET /users
GET /users/{id}
POST /users
PUT /users/{id}
DELETE /users/{id}
```

权限：`user:view|create|update|delete`。不可删除用户名 `admin`。密码长度 12–128。

---

## Role

```
GET /roles
POST /roles
PUT /roles/{id}
DELETE /roles/{id}
```

权限：`role:view|create|update|delete`。管理员角色（`code=admin`）不可删除，且不可通过 API 修改其 `permission_ids`。

---

## Permission

```
GET /permissions
```

权限：`role:view`。返回全量权限列表（不分页）。

---

## Data Center

```
GET /datacenters
POST /datacenters
PUT /datacenters/{id}
DELETE /datacenters/{id}
```

权限：`datacenter:view|create|update|delete`。

---

## Building

```
GET /buildings
POST /buildings
PUT /buildings/{id}
DELETE /buildings/{id}
```

---

## Floor

```
GET /floors
POST /floors
PUT /floors/{id}
DELETE /floors/{id}
```

---

## Room

```
GET /rooms
POST /rooms
POST /rooms/quick
PUT /rooms/{id}
DELETE /rooms/{id}
```

权限：`datacenter:view|create|update|delete`。

### POST /rooms/quick（快速创建）

| Field | Required | Description |
| ----- | -------- | ----------- |
| datacenter_id | ✓ | 已有数据中心 |
| building_no | ✓ | 楼号；不存在则创建 Building |
| room_no | ✓ | 机房编号；写入 Room.name |
| layout_mode | | `auto`（默认）/ `manual` |
| rack_rows / rack_columns | | auto 模式网格 |
| row_layout | | manual：每排机柜数 |
| code_mode | | `auto`（默认）/ `custom` |
| code_prefix | | 默认 `A`；支持 `A-D`、`A-BZ` |
| slot_codes | | custom 时完整矩阵 |
| description | | 可选 |

服务行为：解析数据中心 → 找/建楼栋 → 找/建默认楼层 `1F` → 创建机房并生成布局与 `slot_codes`。前端新建机房仅调用本接口。

响应扩展字段：`datacenter_id`、`datacenter_name`、`location`、`building_no`、`room_no`、`layout_mode`、`rack_rows`、`rack_columns`、`row_layout`、`rack_capacity`、`code_mode`、`code_prefix`、`slot_codes`。

---

## Rack Template

```
GET /rack-templates
POST /rack-templates
PUT /rack-templates/{id}
DELETE /rack-templates/{id}
```

权限：`rack:view|create|update|delete`。种子模板：`STD-42U`、`STD-48U`。

---

## Rack

```
GET /racks
POST /racks
PUT /racks/{id}
DELETE /racks/{id}
GET /racks/{id}/svg
GET /racks/{id}/layout
POST /racks/{id}/layout
```

权限：机柜 CRUD 用 `rack:*`；上架 `POST .../layout` 需 `device:update`。

创建规则：`code` 全局唯一；`name` 机房内唯一；指定 `row_no`+`column_no` 须落在 Room `row_layout` 且空闲；未指定则自动占第一个空闲位；带 `rack_template_id` 时以模板覆盖 `total_u`/`width`/`depth`。

---

## Device

```
GET /devices
POST /devices
PUT /devices/{id}
DELETE /devices/{id}
GET /devices/export?format=xlsx|pdf
GET /devices/import/template
POST /devices/import
```

权限：CRUD 用 `device:*`；导入 `device:import`；导出 `device:export`。

导出列：hostname、serial_number、model_code、model_name、height_u、status、rack_code、u_position、power、weight、description。

导入：模板下载 + multipart `file`；必填 hostname、serial_number、model_code；按 model_code 解析型号并创建未上架设备；响应 `{ created, failed, errors[] }`。

---

## Dashboard

```
GET /dashboard/summary
GET /dashboard/utilization
GET /dashboard/power
GET /dashboard/device-count
```

权限：`dashboard:view`。

---

---

## Layout Engine

```
POST /layout/auto

POST /layout/validate

GET /layout/result
```

---

## SVG

```
GET /svg/rack/{id}

GET /svg/export

POST /svg/render
```

---

## File

```
POST /files/upload

GET /files/{id}

DELETE /files/{id}
```

---

## Audit

```
GET /audit/logs
```

---

# 11 OpenAPI Convention

所有接口：

必须：

- Tag
- Summary
- Description
- Request Schema
- Response Schema
- Example
- Error Example

自动生成：

Swagger

ReDoc

OpenAPI JSON

---

# 12 Security

接口权限：

RBAC

权限粒度：

```
rack:view

rack:create

rack:update

rack:delete

device:view

device:create
```

所有写接口：

必须记录：

Audit Log

---

# 13 Rate Limiting

默认：

```
100 requests/minute
```

登录：

```
10 requests/minute
```

导入：

```
5 requests/minute
```

未来支持：

Redis Limiter

---

# 14 API Lifecycle

开发流程：

```
PRD

↓

Database

↓

OpenAPI

↓

FastAPI

↓

Swagger

↓

Frontend SDK

↓

Testing
```

API 状态：

| Status     | Meaning |
| ---------- | ------- |
| Draft      | 设计中  |
| Stable     | 正式    |
| Deprecated | 废弃    |
| Removed    | 移除    |

---

# Appendix A - REST Resource Naming

| Resource      | URI                    |
| ------------- | ---------------------- |
| Rack          | /racks                 |
| Rack Template | /rack-templates        |
| Room          | /rooms                 |
| Room Quick    | /rooms/quick           |
| Device        | /devices               |
| Device Export | /devices/export        |
| Device Import | /devices/import        |
| User          | /users                 |
| Role          | /roles                 |
| Permission    | /permissions           |
| Dashboard     | /dashboard             |

---

# Appendix B - HTTP Method

| Method | Description    |
| ------ | -------------- |
| GET    | Query          |
| POST   | Create         |
| PUT    | Update         |
| PATCH  | Partial Update |
| DELETE | Delete         |

---

# References

- docs/01-PRD.md
- docs/02-System-Architecture.md
- docs/03-Domain-Model.md
- docs/04-Database-Design.md

---