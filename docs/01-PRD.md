---
title: Product Requirement Document
project: RackDCIM Pro
version: 1.3.0
status: Active
author: Enzo
date: 2026-07-22
last_code_sync: 2026-07-22
category: Product
---

# Product Requirement Document (PRD)

> RackDCIM Pro — AI Native Data Center Infrastructure Management Platform

---

## Document Conventions

| Symbol | Meaning |
| ------ | ------- |
| ✅ | Delivered in V1 |
| 🚧 | Partial |
| 📋 | Future version |

---

## Revision History

| Version | Date | Author | Description |
| ------- | ---- | ------ | ----------- |
| 1.0.0 | 2026-07-16 | Enzo | Initial draft |
| 1.1.0 | 2026-07-17 | Enzo | Room layout & RBAC scope |
| 1.2.0 | 2026-07-22 | Enzo | IP, contracts, profiles |
| 1.3.0 | 2026-07-22 | Enzo | Professional rewrite with acceptance criteria |

---

## 1. Product Overview

### 1.1 Product Identity

| Field | Value |
| ----- | ----- |
| Product name | RackDCIM Pro |
| Chinese name | 智能数据中心基础设施管理平台 |
| Slogan | AI Native Infrastructure Management Platform |
| Current release | 1.0.0 (application) |

### 1.2 Vision

统一数据中心资产数据模型，提供机柜可视化、自动 U 位上架、导入导出与权限管理，替代 Excel 运维模式。

### 1.3 Mission

易部署、易维护、API First、可扩展、AI Ready（架构预留，V1 无 AI 运行时）。

---

## 2. Business Background

### 2.1 Pain Points

| ID | Pain | V1 Solution |
| -- | ---- | ----------- |
| P1 | 机柜利用率无法统计 | Dashboard utilization ✅ |
| P2 | 设备查找效率低 | 设备 CRUD + 机柜 SVG ✅ |
| P3 | 人工维护成本高 | Excel 导入 + 快速建机房 ✅ |
| P4 | 上下架易出错 | Layout conflict detection ✅ |
| P5 | 无法自动规划 | Auto layout + mount API ✅ |
| P6 | 无法预测容量 | 📋 V3 AI |

---

## 3. Target Users

| Persona | Primary Tasks |
| ------- | ------------- |
| 数据中心管理员 | 建机房、机柜、看布局图 |
| 运维工程师 | 设备上下架、IP 绑定 |
| 资产管理员 | 合同、导入导出 |
| 系统管理员 | 用户、角色、权限 |
| 审计人员 | 📋 审计 UI（API ✅） |

---

## 4. Functional Requirements (V1)

### 4.1 Infrastructure (FR-INF)

| ID | Requirement | Priority | Status | Acceptance |
| -- | ----------- | -------- | ------ | ---------- |
| FR-INF-01 | 数据中心 CRUD（含 location） | P0 | ✅ | `/datacenters` + DatacenterView |
| FR-INF-02 | Building/Floor CRUD | P1 | ✅ | API；Room quick 自动创建 |
| FR-INF-03 | Room 快速创建 | P0 | ✅ | `POST /rooms/quick` |
| FR-INF-04 | Room 布局 row_layout | P0 | ✅ | auto/manual 模式 |
| FR-INF-05 | 机柜位编号 slot_codes | P0 | ✅ | auto/custom code_mode |
| FR-INF-06 | 布局图可视化 | P1 | ✅ | RoomView 抽屉 |

### 4.2 Rack (FR-RACK)

| ID | Requirement | Priority | Status | Acceptance |
| -- | ----------- | -------- | ------ | ---------- |
| FR-RACK-01 | 机柜模板 STD-42U/48U | P0 | ✅ | seed + RackView |
| FR-RACK-02 | 机柜位选位创建 | P0 | ✅ | row_no/column_no |
| FR-RACK-03 | 模板批量应用到机房 | P1 | ✅ | apply-to-room |
| FR-RACK-04 | 批量放置机柜 | P1 | ✅ | place-batch |
| FR-RACK-05 | 机柜 SVG | P0 | ✅ | `/racks/{id}/svg` |
| FR-RACK-06 | 机柜 Excel 批量导入 | P2 | 📋 | — |

### 4.3 Device (FR-DEV)

| ID | Requirement | Priority | Status | Acceptance |
| -- | ----------- | -------- | ------ | ---------- |
| FR-DEV-01 | 设备 CRUD | P0 | ✅ | DeviceView |
| FR-DEV-02 | 厂商/型号/类型 catalog | P0 | ✅ | devices.py catalog APIs |
| FR-DEV-03 | Param/System/BMC 配置档 | P1 | ✅ | profile APIs |
| FR-DEV-04 | U 位上架/下架 | P0 | ✅ | layout mount/unmount |
| FR-DEV-05 | Excel 导入 | P0 | ✅ | `/devices/import` |
| FR-DEV-06 | Excel/PDF 导出 | P0 | ✅ | `/devices/export` |
| FR-DEV-07 | 批量删除 | P1 | ✅ | batch-delete |

### 4.4 IP Address (FR-IP)

| ID | Requirement | Priority | Status | Acceptance |
| -- | ----------- | -------- | ------ | ---------- |
| FR-IP-01 | IP CRUD | P0 | ✅ | `/ip-addresses` |
| FR-IP-02 | 批量创建/删除 | P0 | ✅ | batch-create/delete |
| FR-IP-03 | 绑定设备/机柜/范围 | P0 | ✅ | bind, batch-bind |
| FR-IP-04 | 自动分配 | P1 | ✅ | allocate |
| FR-IP-05 | 状态管理 | P1 | ✅ | free/allocated/disabled |

### 4.5 Device Contract (FR-CON)

| ID | Requirement | Priority | Status | Acceptance |
| -- | ----------- | -------- | ------ | ---------- |
| FR-CON-01 | 合同 CRUD | P0 | ✅ | ContractView |
| FR-CON-02 | 明细 Excel 导入 | P1 | ✅ | items/import |
| FR-CON-03 | 绑定/解绑设备 | P1 | ✅ | bind/unbind-devices |
| FR-CON-04 | 合同汇总 | P2 | ✅ | `/summary` |

### 4.6 Security (FR-SEC)

| ID | Requirement | Priority | Status | Acceptance |
| -- | ----------- | -------- | ------ | ---------- |
| FR-SEC-01 | JWT 登录/刷新/登出 | P0 | ✅ | auth endpoints |
| FR-SEC-02 | RBAC 权限 | P0 | ✅ | require_permissions |
| FR-SEC-03 | 用户/角色管理 UI | P0 | ✅ | UserView, RoleView |
| FR-SEC-04 | 默认 admin 种子 | P0 | ✅ | seed.py |
| FR-SEC-05 | 审计日志 | P1 | 🚧 | API ✅, UI 📋 |
| FR-SEC-06 | Rate limiting | P2 | 📋 | — |

### 4.7 Dashboard (FR-DASH)

| ID | Requirement | Priority | Status | Acceptance |
| -- | ----------- | -------- | ------ | ---------- |
| FR-DASH-01 | 汇总统计 | P0 | ✅ | `/dashboard/summary` |
| FR-DASH-02 | 利用率 | P0 | ✅ | `/dashboard/utilization` |
| FR-DASH-03 | 功耗统计 | P2 | 📋 | — |
| FR-DASH-04 | 设备数量趋势 | P2 | 📋 | — |

---

## 5. Non-Functional Requirements

| ID | Category | Requirement | Target | Status |
| -- | -------- | ----------- | ------ | ------ |
| NFR-01 | Performance | API P95 | <500ms (typical CRUD) | 🚧 未压测 |
| NFR-02 | Performance | SVG render | <500ms | 🚧 |
| NFR-03 | Security | HTTPS production | Required | 📋 deploy doc |
| NFR-04 | Security | Password min length | 12 chars | ✅ |
| NFR-05 | Availability | Docker Compose deploy | Single node | ✅ |
| NFR-06 | Maintainability | Code coverage | ≥90% goal | 📋 ~low today |
| NFR-07 | i18n | 中英文 | Full UI | 📋 中文为主 |

---

## 6. Product Scope Summary

### 6.1 Included (V1)

数据中心、机房（快速创建/布局/编号）、机柜（模板/选位/SVG）、设备（档案/上下架/导入导出）、IP、合同、Dashboard、RBAC。

### 6.2 Excluded (V1)

实时监控、工单、UPS/PDU 控制、AI 运行时、MinIO、Celery Worker、审计 UI。

---

## 7. Design Principles

| Principle | Implementation |
| --------- | -------------- |
| API First | All features exposed via REST |
| Configuration First | Rack templates, room layout, code rules |
| Data Driven | Pinia + API, no page-only state |
| AI Native | OpenAPI + structured data for future agents |
| Plugin Architecture | 📋 Future |

---

## 8. Roadmap

| Version | Theme | Key Features |
| ------- | ----- | ------------ |
| V1.0 | Core DCIM | Rack, Device, Layout, IP, Contract, RBAC ✅ |
| V2.0 | Operations | Cable, PDU, UPS, CMDB, LDAP |
| V3.0 | Intelligence | AI Assistant, Prediction, Digital Twin |

---

## Appendix A — Glossary

| Term | Definition |
| ---- | ---------- |
| DCIM | Data Center Infrastructure Management |
| U | Rack unit (1.75") |
| RBAC | Role-Based Access Control |
| slot_codes | 2D matrix of rack position labels in a room |

---

## Appendix B — Non-Goals (V1)

AI 视频识别、IoT 实时采集、大屏监控、自动巡检机器人。

---

## References

- [00-Project.md](00-Project.md)
- [05-API-Design.md](05-API-Design.md)
- [14-Roadmap.md](14-Roadmap.md)
