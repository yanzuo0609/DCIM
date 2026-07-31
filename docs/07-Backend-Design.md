---
title: Backend Design Specification
project: RackDCIM Pro
version: 1.3.0
status: Active
author: Enzo
date: 2026-07-22
last_code_sync: 2026-07-22
category: Backend
tech_stack: FastAPI + SQLAlchemy + PostgreSQL
---

# Backend Software Design Specification (BSD)

> `backend/app/` — Clean architecture with service/repository layers

---

## Revision History

| Version | Date | Author | Description |
| ------- | ---- | ------ | ----------- |
| 1.3.0 | 2026-07-22 | Enzo | Full module map, DI, lifecycle, error handling |

---

## 1. Application Entry

| File | Role |
| ---- | ---- |
| `app/main.py` | FastAPI factory, CORS, lifespan, `/health` |
| `app/api/v1/router.py` | Aggregates 15 endpoint routers |
| `app/core/config.py` | Pydantic Settings from `.env` |
| `app/core/database.py` | Async engine, init_db, SQLite patches |
| `app/core/handlers.py` | Global exception handlers |
| `app/core/dependencies.py` | DI + RBAC |
| `app/core/security.py` | bcrypt + JWT |
| `app/core/seed.py` | Default data |

### 1.1 Lifespan

```python
@asynccontextmanager
async def lifespan(app):
    await init_db()  # create_all + seed + sqlite patches
    yield
```

---

## 2. Configuration

Environment file: `backend/.env` (from `.env.example`).

| Variable | Default | Description |
| -------- | ------- | ----------- |
| DATABASE_URL | sqlite+aiosqlite:///./rackdcim.db | DB connection |
| SECRET_KEY | change-me | JWT signing |
| ACCESS_TOKEN_EXPIRE_MINUTES | 15 | Access TTL |
| REFRESH_TOKEN_EXPIRE_DAYS | 7 | Refresh TTL |
| REDIS_URL | redis://localhost:6379/0 | Cache (future) |
| CELERY_BROKER_URL | redis://.../1 | Celery broker |
| CORS_ORIGINS | localhost:5173 | JSON list |
| DEBUG | true | SQL echo in dev |

---

## 3. Layered Architecture

```text
Endpoint (api/v1/endpoints/*.py)
    ↓ Depends(get_*_service), require_permissions
Service (services/*.py)
    ↓ business rules, orchestration
Repository (repositories/*.py)
    ↓ SQLAlchemy queries
Model (models/*.py)
    ↓ ORM mapping
Database
```

**Domain engine:** `domains/layout/engine.py` — pure U-position logic, called by `LayoutService`.

---

## 4. Endpoint Modules

| # | Module | File | Prefix / Notes |
| - | ------ | ---- | -------------- |
| 1 | health | health.py | /health |
| 2 | auth | auth.py | /auth |
| 3 | dashboard | dashboard.py | /dashboard |
| 4 | datacenters | datacenters.py | /datacenters |
| 5 | buildings | buildings.py | /buildings |
| 6 | floors | floors.py | /floors |
| 7 | rooms | rooms.py | /rooms |
| 8 | racks | racks.py | /racks |
| 9 | rack_templates | rack_templates.py | /rack-templates |
| 10 | devices | devices.py | /devices + catalogs |
| 11 | device_contracts | device_contracts.py | /device-contracts |
| 12 | ip_addresses | ip_addresses.py | /ip-addresses |
| 13 | layout | layout.py | /layout |
| 14 | svg_audit | svg_audit.py | /svg, /audit |
| 15 | users | users.py | /users, /roles, /permissions |

---

## 5. Service Layer

| Service | File | Key Methods |
| ------- | ---- | ----------- |
| AuthService | auth.py | login, refresh, profile |
| InfrastructureService | infrastructure.py | CRUD, quick_create_room |
| RackService | rack.py | CRUD, place_batch, template apply |
| DeviceService | device.py | CRUD, catalog CRUD |
| ExportService | export.py | export_xlsx/pdf, import_devices |
| LayoutService | layout.py | validate, auto, mount, unmount, batch |
| SvgService | svg.py | render_rack_svg |
| DashboardService | dashboard.py | summary, utilization |
| IpAddressService | ip_address.py | CRUD, batch, allocate, bind |
| DeviceContractService | device_contract.py | CRUD, bind, summary |
| ContractExportService | contract_export.py | items template/import |
| UserMgmtService | user_mgmt.py | users, roles |
| AuditService | audit.py | list_logs |

---

## 6. Repository Layer

| Repository | Aggregate roots |
| ---------- | --------------- |
| InfrastructureRepository | DC, Building, Floor, Room |
| RackRepository | Rack, RackTemplate, RackPosition |
| DeviceRepository | Device, catalogs |
| DeviceContractRepository | DeviceContract |
| IpAddressRepository | IpAddress |
| UserRepository | User, Role, Permission |
| AuditRepository | AuditLog |

Base pagination in `repositories/base.py`: soft-delete filter, keyword search hooks.

---

## 7. Schema Layer (Pydantic v2)

| Module | DTOs |
| ------ | ---- |
| common.py | ApiResponse, PaginatedResponse, ErrorResponse, PaginationParams |
| auth.py | LoginRequest, TokenResponse, UserProfile |
| infrastructure.py | RoomQuickCreate, slot code helpers |
| rack.py | RackCreate, RackLayout, PlaceBatch |
| device.py | DeviceCreate, catalog schemas |
| layout.py | MountRequest, ValidateLayoutResponse |
| ip_address.py | IpCreate, batch results |
| device_contract.py | ContractCreate, items import |
| user_mgmt.py | UserCreate, RoleCreate |
| export.py | ImportResult |

---

## 8. Dependency Injection

Pattern in `core/dependencies.py`:

```python
async def get_rack_service(session: AsyncSession = Depends(get_db)) -> RackService:
    return RackService(RackRepository(session), ...)

def require_permissions(*codes: str):
    async def checker(user: User = Depends(get_current_user)):
        if user.has_permission("admin:*"):
            return user
        if not all(user.has_permission(c) for c in codes):
            raise ForbiddenError()
        return user
    return checker
```

---

## 9. Exception Handling

Hierarchy (`core/exceptions.py`):

- `AppError` (base, carries `code`, `message`, `details`)
- `NotFoundError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`, `ValidationError`

Handlers (`core/handlers.py`):

- `AppError` → JSON ErrorResponse + mapped HTTP status
- `RequestValidationError` → 422 with Pydantic errors
- Unhandled → 500 (includes detail in dev)

---

## 10. Security Implementation

| Feature | Implementation |
| ------- | -------------- |
| Password hash | bcrypt via `hash_password()` |
| JWT | HS256, python-jose |
| Token payload | sub=user_id, exp, type=access\|refresh |
| RBAC | Permission codes on Role, checked per endpoint |
| Login lockout fields | failed_login_count, locked_until on User |
| Credential profiles | `credential_crypto.py` for profile payloads |

See [11-Security.md](11-Security.md) for full policy.

---

## 11. Database Initialization

### 11.1 PostgreSQL (Production)

```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 11.2 SQLite (Development)

1. `create_all()` from all models
2. SQLite column patches (mirror Alembic 0003–0016)
3. `seed_defaults()` if empty

Seed creates: permissions, admin role/user, rack templates, device types/models.

---

## 12. Celery 📋

`core/celery_app.py` configures broker/backend URLs. **No tasks defined, no worker in compose.**

Planned tasks: async import, report generation, email.

---

## 13. File Handling

| Format | Library | Service |
| ------ | ------- | ------- |
| Excel | openpyxl | export.py, contract_export.py |
| PDF | reportlab | export.py |

No MinIO; files streamed in HTTP response or multipart upload.

---

## 14. Testing

| Type | Path | CI |
| ---- | ---- | -- |
| Unit | tests/unit/ | ✅ |
| Integration | tests/integration/ | 📋 local only |

Run:

```bash
cd backend && pytest ../tests/unit -v
cd backend && pytest ../tests/integration -v
```

---

## 15. Code Quality

```bash
black app
ruff check app
```

Enforced in CI on push to main/develop.

---

## References

- [05-API-Design.md](05-API-Design.md)
- [08-Layout-Engine.md](08-Layout-Engine.md)
- [04-Database-Design.md](04-Database-Design.md)
