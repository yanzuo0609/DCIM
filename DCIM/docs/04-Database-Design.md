---
title: Database Design Specification
project: RackDCIM Pro
version: 1.0.0
status: Draft
author: Enzo
date: 2026-07-16
category: Database
---

# Database Design Specification

> RackDCIM Pro
>
> Database Design (DDS)

---

# Revision History

| Version | Date       | Author | Description     |
| ------- | ---------- | ------ | --------------- |
| 1.0.0   | 2026-07-16 | Enzo   | Initial Version |
| 1.1.0   | 2026-07-17 | Enzo   | Sync V1: room layout columns, migrations 0003–0005 |

---

# Table of Contents

1. Database Overview
2. Design Principles
3. Naming Convention
4. Data Types
5. Audit Fields
6. Primary Key Strategy
7. Foreign Key Strategy
8. Index Strategy
9. Soft Delete
10. Database Schema
11. Core Tables
12. Relationship Design
13. Constraints
14. Performance Design
15. Backup Strategy
16. Migration Strategy

---

# 1 Database Overview

数据库采用：

```
PostgreSQL 16
```

开发环境：

```
SQLite
```

ORM：

```
SQLAlchemy 2.x
```

Migration：

```
Alembic
```

数据库目标：

- 高性能
- 高一致性
- 易扩展
- 多租户预留
- AI Ready

---

# 2 Design Principles

数据库遵循以下原则：

- Third Normal Form（3NF）
- UUID 主键
- 审计字段统一
- 逻辑删除
- 乐观锁预留
- 全部字段必须备注
- 禁止业务逻辑进入数据库

---

# 3 Naming Convention

## Table

全部小写

snake_case

例如：

```
rack
device
room
user_role
audit_log
```

---

## Column

全部：

snake_case

例如：

```
created_at
updated_at
deleted_at
device_name
rack_id
```

---

## Index

格式：

```
idx_table_column
```

例如：

```
idx_device_hostname
```

---

## Unique

```
uk_table_column
```

例如：

```
uk_rack_code
```

---

## Foreign Key

```
fk_child_parent
```

例如：

```
fk_device_rack
```

---

# 4 Data Types

| Business    | Database      |
| ----------- | ------------- |
| ID          | UUID          |
| Name        | VARCHAR(100)  |
| Code        | VARCHAR(50)   |
| Description | TEXT          |
| Boolean     | BOOLEAN       |
| DateTime    | TIMESTAMP     |
| JSON        | JSONB         |
| Power       | NUMERIC(10,2) |
| Weight      | NUMERIC(10,2) |

---

# 5 Audit Fields

所有业务表统一包含：

| Field      | Type      |
| ---------- | --------- |
| created_at | TIMESTAMP |
| created_by | UUID      |
| updated_at | TIMESTAMP |
| updated_by | UUID      |
| deleted_at | TIMESTAMP |
| deleted_by | UUID      |
| version    | INTEGER   |

说明：

- 支持审计
- 支持乐观锁
- 支持软删除

---

# 6 Primary Key Strategy

统一：

```
UUID
```

示例：

```
id UUID PRIMARY KEY
```

优点：

- 分布式
- 安全
- 避免自增冲突

---

# 7 Foreign Key Strategy

全部采用真实外键。

例如：

```
device

↓

rack

↓

room

↓

floor

↓

building

↓

datacenter
```

保证数据一致性。

---

# 8 Index Strategy

建立以下索引：

- 主键索引
- 唯一索引
- 外键索引
- 查询索引
- 组合索引

例如：

```
hostname

serial_number

rack_id

room_id

(device_type,status)
```

---

# 9 Soft Delete

采用：

```
deleted_at
```

而不是：

```
status=0
```

查询默认：

```
deleted_at IS NULL
```

---

# 10 Database Schema

系统划分以下 Schema：

| Schema | Description |
| ------ | ----------- |
| public | 业务数据    |
| audit  | 审计日志    |
| system | 系统配置    |

---

# 11 Core Tables

## Infrastructure

| Table      |
| ---------- |
| datacenter |
| building   |
| floor      |
| room       |

### room 表关键列（V1）

| Column       | Type         | Notes                                      |
| ------------ | ------------ | ------------------------------------------ |
| floor_id     | UUID FK      | → floor.id                                 |
| name         | VARCHAR(100) | 同楼层唯一（uk_room_floor_name）           |
| description  | TEXT         | 可空                                       |
| rack_rows    | INTEGER      | NOT NULL，默认 4                           |
| rack_columns | INTEGER      | NOT NULL，默认 6                           |
| row_layout   | JSON         | 可空；如 `[6,6,8,4]`；空则均匀网格         |
| code_mode    | VARCHAR(20)  | NOT NULL，默认 `auto`（`auto`/`custom`）  |
| code_prefix  | VARCHAR(50)  | 可空；自动编号前缀表达式                   |
| slot_codes   | JSON         | 可空；机柜位编号矩阵                       |

另含 BaseModel 审计字段：`id`、`created_at`、`created_by`、`updated_at`、`updated_by`、`deleted_at`、`deleted_by`、`version`。

---

## Rack

| Table         |
| ------------- |
| rack          |
| rack_template |
| rack_position |

---

## Device

| Table           |
| --------------- |
| device          |
| device_model    |
| manufacturer    |
| device_category |

---

## Asset

| Table          |
| -------------- |
| asset          |
| vendor         |
| purchase_order |

---

## User

| Table           |
| --------------- |
| user            |
| role            |
| permission      |
| user_role       |
| role_permission |

---

## Dashboard

| Table              |
| ------------------ |
| dashboard_snapshot |

---

## System

| Table         |
| ------------- |
| audit_log     |
| system_config |
| file_storage  |

---

# 12 Relationship Design

```
DataCenter

↓

Building

↓

Floor

↓

Room

↓

Rack

↓

RackPosition

↓

Device
```

权限关系：

```
User

↓

Role

↓

Permission
```

---

# 13 Constraints

必须保证：

- Rack Code 全局唯一
- Device SN / hostname 唯一
- Username / Email 唯一
- Room 在同一 Floor 内 name 唯一
- Room `slot_codes` 机房内大小写不敏感唯一
- Rack `name` 在同一 Room 内唯一
- Rack `(room_id, row_no, column_no)` 位置不冲突（业务层校验）

U 位：

```
Rack + UPosition

Unique
```

禁止重复占用。

缩小 Room 布局时，不得小于已有机柜所在行列。

---

# 14 Performance Design

预计：

```
Rack

10000+

Device

200000+

User

5000+

Audit

10000000+
```

要求：

普通查询：

```
<100ms
```

分页：

```
<500ms
```

Dashboard：

```
<2s
```

---

# 15 Backup Strategy

支持：

- pg_dump
- WAL
- Docker Volume
- 自动备份

未来：

- PostgreSQL Cluster

---

# 16 Migration Strategy

统一：

```
Alembic
```

迁移流程：

```
ORM

↓

Alembic Revision

↓

Review

↓

Migration

↓

Deploy
```

禁止直接修改数据库。

### V1 已落地迁移（room 布局相关）

| Revision | File | 变更 |
| -------- | ---- | ---- |
| 0003 | `0003_add_room_rack_layout.py` | `rack_rows`、`rack_columns` |
| 0004 | `0004_add_room_row_layout.py` | `row_layout` JSON |
| 0005 | `0005_add_room_slot_codes.py` | `code_mode`、`code_prefix`、`slot_codes` |

链：`0002_add_rack_tables` → `0003` → `0004` → `0005`。

### SQLite 开发路径补列

当 `database_url` 以 `sqlite` 开头时，`create_all` 之后由 `_ensure_sqlite_room_columns`（`app/core/database.py`）用 `PRAGMA` + `ALTER TABLE` 补齐上述 room 列，再执行 `seed_defaults`。生产 / PostgreSQL 仍以 Alembic 为准。

---

# Appendix A

## Planned Tables（V1）

| Category       | Table Count |
| -------------- | ----------- |
| Infrastructure | 4           |
| Rack           | 3           |
| Device         | 4           |
| Asset          | 3           |
| User           | 5           |
| System         | 5           |

预计：

```
约25~30张核心业务表
```

V2 将扩展：

- cable
- pdu
- ups
- monitoring
- ipam
- cmdb

---

# References

- docs/02-System-Architecture.md
- docs/03-Domain-Model.md
- docs/05-API-Design.md

---