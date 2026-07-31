---
title: Database Design Specification
project: RackDCIM Pro
version: 1.3.0
status: Active
author: Enzo
date: 2026-07-22
last_code_sync: 2026-07-22
category: Database
---

# Database Design Specification (DDS)

> PostgreSQL 16 (production) · SQLite (development) · SQLAlchemy 2.x · Alembic

---

## Revision History

| Version | Date | Author | Description |
| ------- | ---- | ------ | ----------- |
| 1.3.0 | 2026-07-22 | Enzo | Complete table catalog, migrations 0001–0016, dev/prod paths |

---

## 1. Overview

| Item | Value |
| ---- | ----- |
| ORM | SQLAlchemy 2.x async |
| Migrations | Alembic (`backend/alembic/`) |
| Dev URL | `sqlite+aiosqlite:///./rackdcim.db` |
| Prod URL | `postgresql+asyncpg://...` |
| Init | `init_db()` on app startup |
| Seed | `seed_defaults()` when no users |

---

## 2. Design Principles

- UUID primary keys (distributed-safe)
- 3NF normalized core schema
- Soft delete via `deleted_at`
- Unified audit columns on all business tables
- Business logic in application layer, not DB triggers
- Real foreign keys for referential integrity

---

## 3. Naming Conventions

| Object | Rule | Example |
| ------ | ---- | ------- |
| Table | snake_case singular | `device`, `rack_template` |
| Column | snake_case | `created_at`, `device_model_id` |
| PK | `id` UUID | |
| UK | `uk_{table}_{column}` | `uk_rack_room_code` |
| FK | implicit `_id` suffix | `room_id` → `room.id` |
| Index | `ix_*` / inline `index=True` | |

---

## 4. Standard Column Set (BaseModel)

Every business table includes:

```sql
id              UUID PRIMARY KEY
created_at      TIMESTAMP NOT NULL
created_by      UUID NULL
updated_at      TIMESTAMP NOT NULL
updated_by      UUID NULL
deleted_at      TIMESTAMP NULL
deleted_by      UUID NULL
version         INTEGER NOT NULL DEFAULT 1
```

---

## 5. Table Catalog (V1 — 22 tables)

### 5.1 Infrastructure (4)

| Table | PK | Notable Columns | UK/FK |
| ----- | -- | --------------- | ----- |
| datacenter | id | code, name, location | uk code |
| building | id | datacenter_id, name | FK datacenter |
| floor | id | building_id, name | FK building |
| room | id | floor_id, name, rack_rows, rack_columns, row_layout, code_mode, code_prefix, slot_codes | FK floor; uk (floor_id, name) |

### 5.2 Rack (3)

| Table | PK | Notable Columns | UK/FK |
| ----- | -- | --------------- | ----- |
| rack_template | id | code, total_u, width, depth | uk code |
| rack | id | room_id, code, name, row_no, column_no, total_u, status | uk (room_id, code), uk (room_id, name) |
| rack_position | id | rack_id, u_position, occupied, device_id | FK rack, device |

### 5.3 Device (9)

| Table | UK |
| ----- | -- |
| manufacturer | code |
| device_category | code |
| device_type | code |
| device_param_profile | code |
| device_system_profile | code |
| device_bmc_profile | code |
| device_model | code |
| device_contract | contract_no |
| device | hostname, serial_number |

Device FKs: model, type, profiles, contract, rack.

### 5.4 IP (1)

| Table | UK | Notable |
| ----- | -- | ------- |
| ip_address | system_ip | bmc_ip, vip, status, bind_type, scope_rack_ids JSON |

### 5.5 Identity (5)

| Table | Purpose |
| ----- | ------- |
| users | Accounts |
| role | RBAC roles |
| permission | Permission codes |
| user_role | M:N |
| role_permission | M:N |

### 5.6 System (1)

| Table | Purpose |
| ----- | ------- |
| audit_log | Action audit trail |

### 5.7 Planned (not created)

`asset`, `vendor`, `purchase_order`, `dashboard_snapshot`, `system_config`, `file_storage`.

---

## 6. Relationship Hierarchy

```text
datacenter
  └── building
        └── floor
              └── room
                    └── rack
                          └── rack_position ← device (when mounted)

device ──→ device_model ──→ manufacturer
       ──→ device_type / profiles / device_contract
       ←── ip_address (optional bind)

users ←→ role ←→ permission
```

---

## 7. Constraints & Invariants

| Constraint | Enforcement |
| ---------- | ----------- |
| Rack code per room | DB uk_rack_room_code + service |
| Device hostname/SN | DB unique + service |
| IP system_ip | DB unique |
| U position overlap | Service (layout engine) |
| Room layout shrink | Service validation |
| slot_codes uniqueness | Service (case-insensitive) |
| Admin protection | Service (user_mgmt) |

---

## 8. Alembic Migration Chain

| Rev | File | Change |
| --- | ---- | ------ |
| 0001 | initial | DC, user, RBAC, building, floor, room |
| 0002 | add_rack_tables | rack_template, rack, rack_position |
| 0003 | add_room_rack_layout | rack_rows, rack_columns |
| 0004 | add_room_row_layout | row_layout JSON |
| 0005 | add_room_slot_codes | code_mode, code_prefix, slot_codes |
| 0006 | rack_code_unique_per_room | uk (room_id, code) |
| 0007 | device_types_and_profiles | device_type, profiles, device FKs |
| 0008 | bmc_profile | device_bmc_profile |
| 0009 | ip_address | ip_address table |
| 0010 | ip_network_fields | netmask, gateway, dns |
| 0011 | ip_address_status | status column |
| 0012 | device_contract | device_contract, device.contract_id |
| 0013 | contract_manual_fields | manual name fields |
| 0014 | contract_multi_names | JSON name arrays |
| 0015 | contract_manufacturer_names | manufacturer_names |
| 0016 | contract_items_total | device_items, contract_total |

**Production deploy:**

```bash
cd backend
alembic upgrade head
```

---

## 9. Development (SQLite) Path

When `database_url` starts with `sqlite`:

1. `Base.metadata.create_all()` creates all ORM tables
2. `_ensure_sqlite_*` patches in `core/database.py` align columns with migrations 0003–0016
3. `seed_defaults()` runs if no users exist

This allows zero-config local dev without running Alembic. **Production must use Alembic**, not rely on create_all patches.

---

## 10. Index Strategy

| Pattern | Tables |
| ------- | ------ |
| FK indexes | All `*_id` foreign keys |
| Lookup | device.hostname, device.serial_number, ip_address.system_ip |
| Filter | ip_address.status, device.status |
| Pagination | created_at (default sort) |

---

## 11. Performance & Capacity

| Entity | Expected Scale | Query Target |
| ------ | -------------- | -------------- |
| rack | 10,000+ | <100ms list |
| device | 200,000+ | paginated <500ms |
| audit_log | 10M+ | indexed time range |
| dashboard | aggregate | <2s |

---

## 12. Backup Strategy

| Environment | Method |
| ----------- | ------ |
| PostgreSQL | pg_dump daily; WAL optional |
| SQLite dev | Copy `rackdcim.db` |
| Docker | Volume `postgres_data` |

---

## References

- [03-Domain-Model.md](03-Domain-Model.md)
- [05-API-Design.md](05-API-Design.md)
- [12-Deployment.md](12-Deployment.md)
