---
title: Domain Model Design
project: RackDCIM Pro
version: 1.0.0
status: Draft
author: Enzo
date: 2026-07-16
category: Domain Model
---

# Domain Model Design

> RackDCIM Pro  
> AI Native Data Center Infrastructure Management Platform

---

# Revision History

| Version | Date       | Author | Description     |
| ------- | ---------- | ------ | --------------- |
| 1.0.0   | 2026-07-16 | Enzo   | Initial Version |
| 1.1.0   | 2026-07-17 | Enzo   | Sync V1 implementation: Room layout, rack numbering, RBAC |

---

# Table of Contents

1. Domain Overview
2. Domain-Driven Design Principles
3. Bounded Context
4. Aggregate Design
5. Entity Model
6. Value Objects
7. Domain Services
8. Domain Events
9. Repository Design
10. Domain Relationships
11. Business Rules
12. Future Expansion

---

# 1. Domain Overview

RackDCIM Pro 基于 Domain Driven Design（DDD）设计。

系统将业务拆分为多个独立领域（Bounded Context），每个领域负责自己的业务逻辑和数据，不直接依赖数据库表结构。

设计目标：

- 高内聚
- 低耦合
- 易维护
- 易扩展
- 支持微服务拆分
- 支持插件化扩展

---

# 2. Domain-Driven Design Principles

采用以下设计原则：

- Entity（实体）
- Value Object（值对象）
- Aggregate（聚合）
- Aggregate Root（聚合根）
- Repository（仓储）
- Domain Service（领域服务）
- Domain Event（领域事件）

所有业务逻辑只能存在于 Domain 层，不允许写在 Controller 中。

---

# 3. Bounded Context

整个系统划分为以下业务域：

| Domain         | Description      |
| -------------- | ---------------- |
| Infrastructure | 数据中心基础设施 |
| Rack           | 机柜管理         |
| Device         | 设备管理         |
| Layout         | 自动布局         |
| Visualization  | SVG 可视化       |
| Dashboard      | 统计分析         |
| Asset          | 资产管理         |
| User           | 用户权限         |
| Audit          | 审计日志         |
| AI             | AI 服务          |

---

# 4. Aggregate Design

## Infrastructure Aggregate

聚合根：

- DataCenter

实体：

- Building
- Floor
- Room

关系：

```
DataCenter
    └── Building
          └── Floor
                └── Room
```

---

## Rack Aggregate

聚合根：

Rack

实体：

- RackTemplate
- RackPosition

说明：

RackPosition 不允许单独存在。

必须依赖 Rack。

---

## Device Aggregate

聚合根：

Device

实体：

- DeviceModel
- Manufacturer
- DeviceCategory

---

## User Aggregate

聚合根：

User

实体：

- Department
- Role
- Permission

---

## Asset Aggregate

聚合根：

Asset

实体：

- PurchaseInfo
- Warranty
- Vendor

---

# 5. Entity Model

## DataCenter

属性：

| Field       | Type   |
| ----------- | ------ |
| id          | UUID   |
| code        | String |
| name        | String |
| location    | String |
| description | String |

---

## Building

属性：

| Field         | Type   |
| ------------- | ------ |
| id            | UUID   |
| datacenter_id | UUID   |
| name          | String |

---

## Floor

属性：

| Field       | Type   |
| ----------- | ------ |
| id          | UUID   |
| building_id | UUID   |
| name        | String |

---

## Room

持久化属性：

| Field        | Type    | Description                                      |
| ------------ | ------- | ------------------------------------------------ |
| id           | UUID    | 主键                                             |
| floor_id     | UUID    | 所属楼层                                         |
| name         | String  | 机房编号（业务上等同 room_no）                   |
| description  | Text    | 描述                                             |
| rack_rows    | Integer | 机柜排数（冗余，等于 row_layout 长度）           |
| rack_columns | Integer | 每排最大机柜数                                   |
| row_layout   | JSON    | 每排机柜数，如 `[6,6,8,4]`；空则均匀网格         |
| code_mode    | String  | `auto` / `custom` 机柜编号模式                   |
| code_prefix  | String  | 自动编号前缀：单字母 `A` 或范围 `A-D` / `A-BZ` |
| slot_codes   | JSON    | 机柜位编号矩阵，如 `[["A01","A02"],["B01"]]`     |

API 响应扩展字段（由层级关联推导）：

| Field           | Description                                      |
| --------------- | ------------------------------------------------ |
| datacenter_id   | 所属数据中心                                     |
| datacenter_name | 数据中心名称                                     |
| location        | 地理位置（来自数据中心）                         |
| building_no     | 机房楼号（Building.name）                        |
| room_no         | 机房编号（= name）                               |
| layout_mode     | `auto`（均匀）/ `manual`（不等宽排）             |
| rack_capacity   | 机柜位总数 = sum(row_layout)                     |

**快速创建（Quick Create）约定：**

1. 必选已存在的 DataCenter（`datacenter_id`）
2. 填写 `building_no`、`room_no`
3. 若楼栋 / 默认楼层（`1F`）不存在则自动创建
4. 布局：`layout_mode=auto` 用 `rack_rows × rack_columns`；`manual` 用 `row_layout`
5. 编号：`code_mode=auto` 按排字母前缀 + 列序号生成；`custom` 使用完整 `slot_codes`

---

## Rack

属性：

| Field            | Type    | Description                    |
| ---------------- | ------- | ------------------------------ |
| id               | UUID    | 主键                           |
| room_id          | UUID    | 所属机房                       |
| rack_template_id | UUID?   | 模板（可空，自定义 U）         |
| code             | String  | 机柜编码（全局唯一）           |
| name             | String  | 机柜名称（机房内唯一）         |
| row_no           | Integer | 所在排（1-based）              |
| column_no        | Integer | 所在列（1-based）              |
| total_u          | Integer | U 位数                         |
| width            | Integer | 宽度 mm                        |
| depth            | Integer | 深度 mm                        |
| status           | Enum    | active / inactive / maintenance |
| description      | Text    | 描述                           |

约束：`(row_no, column_no)` 必须落在所属 Room 的 `row_layout` 内；同一位置不可重复占用。

---

## RackPosition

属性：

| Field      | Type    |
| ---------- | ------- |
| rack_id    | UUID    |
| u_position | Integer |
| occupied   | Boolean |
| device_id  | UUID?   |

---

## Device

属性：

| Field           | Type     |
| --------------- | -------- |
| id              | UUID     |
| hostname        | String   |
| serial_number   | String   |
| device_model_id | UUID     |
| rack_id         | UUID?    |
| u_position      | Integer? |
| height_u        | Integer  |
| weight          | Decimal? |
| power           | Decimal? |
| status          | String   |
| description     | Text?    |

---

## User

属性：

| Field              | Type      |
| ------------------ | --------- |
| id                 | UUID      |
| username           | String    |
| password_hash      | String    |
| email              | String    |
| full_name          | String?   |
| status             | Enum      |
| failed_login_count | Integer   |
| locked_until       | DateTime? |

种子默认管理员：`admin` / `Admin@12345678`（生产环境必须修改）。

---

# 6. Value Objects

## RackSize

包含：Width、Height、Depth。不可修改。

## RoomSlotCode

机房内机柜位编号：

- 自动：`{排字母前缀}{列序号}`，如 `A01`、`B02`（Excel 风格字母，支持 `AA` 等）
- 自定义：任意唯一字符串（≤50）

## RackLocation

包含：`room_id`、`row_no`、`column_no`。

## DeviceSize

包含：Height(U)、Depth、Weight。

## DevicePower

包含：Rated Power、Actual Power。

---

# 7. Domain Services

## LayoutService

负责：

- 自动布局
- U位冲突检测
- 空闲位置计算
- 自动编号

---

## DashboardService

负责：

- 利用率统计
- 容量统计
- 功耗统计

---

## AssetService

负责：

- 生命周期
- 保修
- 采购信息

---

## AIService

负责：

- AI问答
- AI推荐
- AI容量预测

---

# 8. Domain Events

采用事件驱动设计。

事件如下：

| Event           | Description |
| --------------- | ----------- |
| DeviceCreated   | 新增设备    |
| DeviceRemoved   | 删除设备    |
| RackCreated     | 新增机柜    |
| RackUpdated     | 修改机柜    |
| LayoutCompleted | 布局完成    |
| ImportCompleted | 导入完成    |

未来支持 Event Bus。

---

# 9. Repository Design

每个 Aggregate Root 对应一个 Repository。

例如：

```
RackRepository

DeviceRepository

RoomRepository

UserRepository

AssetRepository
```

Repository 负责：

- 查询
- 保存
- 删除
- 分页

不得包含业务逻辑。

---

# 10. Domain Relationships

```
DataCenter
    └── Building
          └── Floor
                └── Room
                      └── Rack
                            └── RackPosition
                                  └── Device
```

另一条关系：

```
User
    ├── Role
    └── Permission
```

---

# 11. Business Rules

## Room

- 快速创建必须关联已有 DataCenter
- `row_layout` 每排机柜数 1–50，排数 1–50
- 缩小布局不得小于已有机柜所在行列
- `slot_codes` 在机房内全局唯一（大小写不敏感）
- 自动编号：单字母从前缀起按排递增；范围（如 `A-D`、`A-BZ`）字母数必须 ≥ 排数

## Rack

- 属于一个 Room
- `code` 全局唯一；`name` 在同一 Room 内唯一
- `(row_no, column_no)` 必须在 Room 布局范围内且未被占用
- 模板可选 STD-42U / STD-48U，或自定义 `total_u`（1–60）

## Device

- 只能放入一个 Rack
- 占用多个连续 U 位
- 不允许 U 位重叠（业务码 10004）

## Layout（设备 U 位）

自动布局必须保证：

- 无冲突
- 不越界
- 支持预留 U 位

## User

- 可拥有多个角色
- 一个角色可包含多个权限
- 默认管理员账号不可删除
- 管理员角色权限不可通过 API 随意清空

---

# 12. Future Expansion

未来可增加以下领域：

- Cable Domain
- PDU Domain
- UPS Domain
- IPAM Domain
- CMDB Domain
- Monitoring Domain
- Digital Twin Domain

所有新领域均采用独立 Bounded Context，不影响现有 Domain。

---

# References

- docs/00-Project.md
- docs/01-PRD.md
- docs/02-System-Architecture.md
- docs/04-Database-Design.md

---