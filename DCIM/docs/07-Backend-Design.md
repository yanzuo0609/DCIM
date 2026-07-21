---
title: Backend Design Specification
project: RackDCIM Pro
version: 1.0.0
status: Draft
author: Enzo
date: 2026-07-16
category: Backend
tech_stack: FastAPI + SQLAlchemy + PostgreSQL
---

# Backend Design Specification

> RackDCIM Pro
>
> Backend Software Design Specification (BSD)

---

# Revision History

| Version | Date       | Author | Description     |
| ------- | ---------- | ------ | --------------- |
| 1.0.0   | 2026-07-16 | Enzo   | Initial Version |
| 1.1.0   | 2026-07-17 | Enzo   | Sync V1 services: room quick, export, user_mgmt |

---

# Table of Contents

1. Backend Overview
2. Architecture Principles
3. Technology Stack
4. Project Structure
5. Layered Architecture
6. Dependency Injection
7. Configuration Management
8. Authentication & Authorization
9. Exception Handling
10. Logging
11. ORM Design
12. Repository Pattern
13. Service Layer
14. Task Queue
15. File Management
16. Cache Design
17. Event Mechanism
18. Testing Strategy
19. Performance Optimization
20. Future Evolution

---

# 1. Backend Overview

Backend 基于 **Python 3.12 + FastAPI** 构建，遵循：

- API First
- DDD（Domain Driven Design）
- SOLID
- Clean Architecture
- Repository Pattern
- Dependency Injection

系统目标：

- 高性能
- 高可维护性
- 高扩展性
- AI Ready
- 支持容器化部署

---

# 2. Architecture Principles

遵循以下原则：

- Single Responsibility
- Open/Closed
- Dependency Inversion
- Separation of Concerns
- Domain First
- Interface Driven

禁止：

- Controller 写业务逻辑
- ORM 泄漏到 View
- SQL 出现在 Controller

---

# 3. Technology Stack

| Layer          | Technology        |
| -------------- | ----------------- |
| Language       | Python 3.12       |
| Framework      | FastAPI           |
| ORM            | SQLAlchemy 2.x    |
| Migration      | Alembic           |
| Validation     | Pydantic v2       |
| Database       | PostgreSQL 16     |
| Cache          | Redis             |
| Task Queue     | Celery            |
| Storage        | MinIO             |
| Authentication | JWT               |
| Password Hash  | BCrypt            |
| Configuration  | Pydantic Settings |

---

# 4. Project Structure

```text
backend/
├── app/
│   ├── api/v1/endpoints/   # auth, rooms, racks, devices, users, …
│   ├── core/               # config, database, seed, dependencies
│   ├── models/
│   ├── schemas/            # 含编号辅助：expand_row_prefixes 等
│   ├── repositories/
│   ├── services/           # infrastructure, rack, export, user_mgmt, …
│   ├── middleware/
│   ├── utils/
│   └── main.py
├── alembic/versions/       # 0001…0005（含 room 布局迁移）
├── tests/
├── requirements.txt
└── pyproject.toml
```

### V1 关键服务

| Service | 职责 |
| ------- | ---- |
| infrastructure | DataCenter / Building / Floor / Room；`quick_create_room` |
| rack | 机柜 CRUD、机柜位解析、U 位布局、SVG |
| export | 设备 Excel/PDF 导出、导入模板与导入 |
| user_mgmt | 用户 / 角色 / 权限 |
| seed | 默认权限、admin、机柜模板、样例型号 |

开发库（SQLite）：`database.py` 在 `create_all` 后 `_ensure_sqlite_room_columns`，再 `seed_defaults`。

---

# 5. Layered Architecture

```
API Layer
     │
Service Layer
     │
Domain Layer
     │
Repository Layer
     │
Database
```

职责：

- API：接收请求、参数校验、返回响应
- Service：业务编排
- Domain：核心业务规则
- Repository：数据访问
- Database：持久化

---

# 6. Dependency Injection

采用 FastAPI Depends。

示例：

```python
@app.get("/racks")
def list_racks(service: RackService = Depends(get_rack_service)):
    return service.list()
```

依赖统一在 `core/dependencies.py` 中管理。

---

# 7. Configuration Management

采用环境变量 + `.env`。

主要配置：

```
DATABASE_URL
REDIS_URL
SECRET_KEY
MINIO_ENDPOINT
JWT_EXPIRE_MINUTES
LOG_LEVEL
```

开发、测试、生产环境分别维护配置文件。

---

# 8. Authentication & Authorization

认证：

- JWT Access Token
- Refresh Token

授权：

- RBAC
- Resource Permission
- Action Permission

示例权限：

```
admin:*
datacenter:view|create|update|delete
rack:view|create|update|delete
device:view|create|update|delete|import|export
user:view|create|update|delete
role:view|create|update|delete
dashboard:view
audit:view
```

实现：`core/dependencies.py` 的 `require_permissions`；`admin:*` 短路放行。

---

# 9. Exception Handling

统一异常结构：

```json
{
  "code": 10002,
  "message": "Rack Conflict",
  "details": {}
}
```

异常分类：

- ValidationError
- BusinessError
- PermissionError
- DatabaseError
- SystemError

---

# 10. Logging

采用结构化日志（JSON）。

日志级别：

- DEBUG
- INFO
- WARNING
- ERROR
- CRITICAL

记录内容：

- Request ID
- User ID
- API
- Duration
- Status Code

---

# 11. ORM Design

所有模型继承：

```python
BaseModel
```

公共字段：

- id
- created_at
- updated_at
- deleted_at
- version

关系：

- One-to-One
- One-to-Many
- Many-to-Many

禁止在 ORM 中编写复杂业务逻辑。

---

# 12. Repository Pattern

每个聚合根对应一个 Repository：

```
RackRepository
DeviceRepository
UserRepository
RoomRepository
```

职责：

- CRUD
- Query
- Pagination
- Transaction

---

# 13. Service Layer

Service 负责业务编排。

示例：

```
RackService
DeviceService
LayoutService
DashboardService
AIService
```

原则：

- 调用多个 Repository
- 执行业务规则
- 发布领域事件

---

# 14. Task Queue

采用 Celery。

异步任务：

- Excel 导入
- PDF 导出
- SVG 渲染
- 邮件通知
- AI 分析

Broker：

```
Redis
```

---

# 15. File Management

对象存储：

MinIO

目录：

```
uploads/
exports/
templates/
reports/
```

支持：

- Excel
- PDF
- SVG
- PNG
- ZIP

---

# 16. Cache Design

Redis 缓存：

- Dashboard
- 系统配置
- 用户权限
- Token 黑名单

缓存策略：

- TTL
- 主动失效
- 写后更新

---

# 17. Event Mechanism

采用领域事件。

示例：

```
DeviceCreated
RackUpdated
LayoutCompleted
ImportFinished
```

后续可扩展：

- Kafka
- RabbitMQ

---

# 18. Testing Strategy

测试分类：

- Unit Test
- Integration Test
- API Test
- Performance Test

工具：

- Pytest
- HTTPX
- Faker

目标覆盖率：

```
>90%
```

---

# 19. Performance Optimization

优化措施：

- SQL 优化
- Redis 缓存
- 异步任务
- 数据分页
- 批量写入
- 连接池

性能目标：

| 指标                      | 目标   |
| ------------------------- | ------ |
| API 响应                  | <200ms |
| 数据库查询                | <100ms |
| Excel 导入（1000 台设备） | <10s   |
| SVG 渲染                  | <500ms |

---

# 20. Future Evolution

规划：

- GraphQL
- gRPC
- Event Bus
- Multi-Tenant
- Plugin System
- AI Agent Service
- MCP Server

Backend 保持向后兼容。

---

# References

- docs/02-System-Architecture.md
- docs/03-Domain-Model.md
- docs/04-Database-Design.md
- docs/05-API-Design.md
- docs/06-Frontend-Design.md

---