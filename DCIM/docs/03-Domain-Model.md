---
title: Domain Model Design
project: RackDCIM Pro
version: 1.3.0
status: Active
author: Enzo
date: 2026-07-22
last_code_sync: 2026-07-22
category: Domain Model
---

# Domain Model Design

> Bounded contexts, aggregates, entities — aligned with `backend/app/models/`

---

## Revision History

| Version | Date | Author | Description |
| ------- | ---- | ------ | ----------- |
| 1.3.0 | 2026-07-22 | Enzo | Full entity catalog with constraints & code paths |

---

## 1. Bounded Contexts

| Context | Aggregate Root | ORM Module | Status |
| ------- | -------------- | ---------- | ------ |
| Infrastructure | DataCenter | `infrastructure.py` | ✅ |
| Rack | Rack | `rack.py` | ✅ |
| Device | Device | `device.py` | ✅ |
| IP Address | IpAddress | `ip_address.py` | ✅ |
| Identity | User | `user.py` | ✅ |
| Audit | AuditLog | `audit.py` | ✅ API |
| Asset | Asset | — | 📋 |

---

## 2. Entity Relationship (Core)

```mermaid
erDiagram
  DataCenter ||--o{ Building : contains
  Building ||--o{ Floor : contains
  Floor ||--o{ Room : contains
  Room ||--o{ Rack : contains
  Rack ||--o{ RackPosition : has
  RackPosition o--o| Device : occupies
  Device }o--|| DeviceModel : references
  DeviceModel }o--|| Manufacturer : references
  Device }o--o| DeviceContract : optional
  Device ||--o{ IpAddress : binds
  User }o--o{ Role : via user_role
  Role }o--o{ Permission : via role_permission
```

---

## 3. Base Model

All business entities inherit `BaseModel` (`models/base.py`):

| Column | Type | Purpose |
| ------ | ---- | ------- |
| id | UUID | Primary key |
| created_at | datetime | Audit |
| created_by | UUID? | Audit |
| updated_at | datetime | Audit |
| updated_by | UUID? | Audit |
| deleted_at | datetime? | Soft delete |
| deleted_by | UUID? | Soft delete |
| version | int | Optimistic lock |

**Query convention:** `deleted_at IS NULL`.

---

## 4. Infrastructure Context

### 4.1 DataCenter

| Field | Type | Constraints |
| ----- | ---- | ----------- |
| code | string(50) | uk_datacenter_code |
| name | string(100) | |
| location | string(200)? | Geographic label |
| description | text? | |

### 4.2 Building / Floor

| Entity | Key Fields |
| ------ | ---------- |
| Building | datacenter_id, name (building_no in API) |
| Floor | building_id, name (default `1F` on quick create) |

### 4.3 Room

| Field | Type | Business Rule |
| ----- | ---- | ------------- |
| floor_id | UUID FK | Required |
| name | string(100) | Unique per floor |
| rack_rows | int | Default 4; synced with row_layout |
| rack_columns | int | Default 6; uniform grid |
| row_layout | JSON | e.g. `[6,6,8,4]`; sum = capacity |
| code_mode | string | `auto` \| `custom` |
| code_prefix | string? | `A`, `A-D`, `A-BZ` |
| slot_codes | JSON | 2D label matrix |

**Quick create** (`InfrastructureService.quick_create_room`):

1. Require existing `datacenter_id`
2. Find or create `Building` by `building_no`
3. Find or create `Floor` named `1F`
4. Generate `row_layout` + `slot_codes`
5. Return enriched response (datacenter_name, rack_capacity, …)

**Helpers:** `expand_row_prefixes`, `generate_slot_codes` in `schemas/infrastructure.py`.

---

## 5. Rack Context

### 5.1 RackTemplate

| Field | Type | Seed Values |
| ----- | ---- | ----------- |
| code | string | STD-42U, STD-48U |
| total_u | int | 42, 48 |
| width, depth | int mm | 600×1000, 600×1200 |

### 5.2 Rack

| Field | Type | Constraint |
| ----- | ---- | ---------- |
| room_id | UUID | FK room |
| code | string(50) | **Unique per room** (uk_rack_room_code) |
| name | string(100) | Unique per room |
| row_no, column_no | int | Within row_layout, not occupied |
| total_u | int | 1–60; from template if set |
| status | enum | active / inactive / maintenance |

### 5.3 RackPosition

| Field | Type | Rule |
| ----- | ---- | ---- |
| rack_id | UUID | Parent rack |
| u_position | int | 1 = bottom |
| occupied | bool | |
| device_id | UUID? | Set when mounted |

**Invariant:** One device occupies contiguous U slots; no overlap (code 10004).

---

## 6. Device Context

### 6.1 Catalog Entities

| Entity | Table | Unique Key |
| ------ | ----- | ---------- |
| Manufacturer | manufacturer | code |
| DeviceCategory | device_category | code |
| DeviceType | device_type | code (system types protected) |
| DeviceParamProfile | device_param_profile | code |
| DeviceSystemProfile | device_system_profile | code |
| DeviceBmcProfile | device_bmc_profile | code |
| DeviceModel | device_model | code |

Seed types: `compute`, `storage`, `network`, `security`.

Seed models: `R750-2U` (DELL), `SW-1U` (HPE).

### 6.2 Device

| Field | Type | Constraint |
| ----- | ---- | ---------- |
| hostname | string(100) | uk_device_hostname |
| serial_number | string(100) | uk_device_serial_number |
| device_model_id | UUID | Required |
| device_type_id | UUID? | |
| param/system/bmc_profile_id | UUID? | |
| contract_id | UUID? | |
| rack_id, u_position | UUID?, int? | Set when mounted |
| height_u | int | Default from model |
| status | enum | stock / mounted / maintenance / retired |

### 6.3 DeviceContract

| Field | Type | Notes |
| ----- | ---- | ----- |
| contract_no | string(100) | uk_device_contract_no |
| device_items | JSON? | Line items array |
| device_names, device_model_names, manufacturer_names | JSON? | Search helpers |
| quantity | int | Sum of items |
| contract_total | decimal? | Total price |
| price_unit | string | yuan / wan |
| purchase_date | date? | |

---

## 7. IP Address Context

| Field | Type | Rule |
| ----- | ---- | ---- |
| system_ip | string(64) | uk_ip_address_system_ip |
| bmc_ip, vip | string? | |
| netmask, gateway, dns, dns_secondary | string? | Added in 0010 |
| status | enum | free / allocated / disabled |
| bind_type | enum | none / device / rack / rack_range |
| device_id, rack_id, room_id | UUID? | Per bind_type |
| scope_rack_ids | JSON? | rack_range binding |
| u_position | int? | Optional 1U spacing rule on allocate |

Service: `app/services/ip_address.py` — batch create max 1024 per request.

---

## 8. Identity Context

### 8.1 User

| Field | Notes |
| ----- | ----- |
| username | Unique; `admin` protected |
| password_hash | bcrypt |
| email | Unique |
| status | active / inactive / locked |
| failed_login_count, locked_until | Lockout fields |

Default seed: `admin` / `Admin@12345678` — **change in production**.

### 8.2 Role & Permission

Many-to-many via `user_role`, `role_permission`.

Permission codes: see [11-Security.md](11-Security.md). Wildcard: `admin:*`.

**Protected:** role `code=admin` cannot be deleted or stripped of permissions via API.

---

## 9. Domain Services

| Service | File | Responsibilities |
| ------- | ---- | ---------------- |
| InfrastructureService | `services/infrastructure.py` | DC/Building/Floor/Room, quick create |
| RackService | `services/rack.py` | Rack CRUD, place-batch, templates |
| DeviceService | `services/device.py` | Device + catalog CRUD |
| LayoutService | `services/layout.py` | validate, auto, mount, unmount, batch |
| IpAddressService | `services/ip_address.py` | IP lifecycle |
| DeviceContractService | `services/device_contract.py` | Contract + bind |
| DashboardService | `services/dashboard.py` | Aggregations |
| SvgService | `services/svg.py` | Rack SVG string |
| ExportService | `services/export.py` | Excel/PDF |
| UserMgmtService | `services/user_mgmt.py` | Users, roles |
| AuditService | `services/audit.py` | Log query |

Layout algorithm core: `domains/layout/engine.py`.

---

## 10. Business Rules Summary

| Rule ID | Domain | Description | Error Code |
| ------- | ------ | ----------- | ---------- |
| BR-R-01 | Rack | code unique within room | 10002 |
| BR-R-02 | Rack | slot not occupied | 10002 |
| BR-R-03 | Rack | row/col within layout | 10004 |
| BR-D-01 | Device | hostname/SN unique | 10003 |
| BR-D-02 | Device | U positions contiguous, no overlap | 10004 |
| BR-D-03 | Device | system device_type not deletable | 10004 |
| BR-RM-01 | Room | cannot shrink layout below existing racks | 10004 |
| BR-RM-02 | Room | slot_codes unique case-insensitive | 10004 |
| BR-IP-01 | IP | max 1024 batch create | 10004 |
| BR-U-01 | User | admin user/role protected | 403 |

Mapping: `core/handlers.py` → HTTP status for 10001–10005.

---

## 11. Repositories

| Repository | File | Aggregate |
| ---------- | ---- | --------- |
| InfrastructureRepository | `repositories/infrastructure.py` | Room hierarchy |
| RackRepository | `repositories/rack.py` | Rack |
| DeviceRepository | `repositories/device.py` | Device |
| DeviceContractRepository | `repositories/device_contract.py` | Contract |
| IpAddressRepository | `repositories/ip_address.py` | IP |
| UserRepository | `repositories/user.py` | User |
| AuditRepository | `repositories/audit.py` | AuditLog |
| BaseRepository | `repositories/base.py` | Shared pagination |

---

## 12. Future Expansion

| Context | Version | Notes |
| ------- | ------- | ----- |
| Asset / Warranty | V2 | purchase_order tables |
| Cable | V2 | New bounded context |
| Full IPAM | V2 | Subnet, VLAN |
| AI | V3 | Tool calls over OpenAPI |

---

## References

- [04-Database-Design.md](04-Database-Design.md)
- [05-API-Design.md](05-API-Design.md)
- [08-Layout-Engine.md](08-Layout-Engine.md)
