---
title: RackDCIM Pro Project Overview
version: 1.0.0
status: Draft
author: Enzo
date: 2026-07-16
type: Project Overview
---

# RackDCIM Pro

> AI Native Data Center Infrastructure Management Platform

---

# Revision History

| Version | Date       | Author | Description     |
| ------- | ---------- | ------ | --------------- |
| 1.0.0   | 2026-07-16 | Enzo   | Initial Version |
| 1.1.0   | 2026-07-17 | Enzo   | Sync V1 scope: room layout, RBAC UI, import/export |

---

# Table of Contents

1. Project Introduction
2. Vision
3. Objectives
4. Product Scope
5. Technology Stack
6. Repository Structure
7. Documentation Structure
8. Development Workflow
9. Coding Standards
10. Version Strategy
11. Branch Strategy
12. Milestones
13. Future Planning
14. License

---

# 1 Project Introduction

## 1.1 Background

随着数字化建设的发展，企业数据中心规模不断扩大。

越来越多的企业拥有：

- 数据中心
- GPU服务器
- AI训练集群
- Kubernetes平台
- OpenStack私有云
- VMware集群
- 网络设备
- 存储设备

然而大量企业仍然依赖Excel维护设备信息。

导致：

- 数据重复
- 更新困难
- 无法多人协同
- 无法容量规划
- 无法统计利用率
- 无法自动生成机柜图
- 无法进行智能分析

因此需要建设一套轻量、高性能、可扩展的数据中心基础设施管理平台。

---

## 1.2 Project Positioning

RackDCIM Pro 是一款 AI Native 的 DCIM 平台。

定位：

- 企业级
- 私有化部署
- 模块化设计
- AI驱动
- 开放API
- 可持续演进

---

# 2 Vision

打造一套现代化的数据中心基础设施管理平台。

帮助企业实现：

- 数据可视化
- 资源数字化
- 自动化运维
- 智能容量规划
- AI辅助管理

---

# 3 Objectives

Version 1.0

完成：

- 数据中心管理（含地理位置）
- 机房快速创建（布局 + 机柜位编号 + 布局图）
- 机柜管理（模板 42U/48U、机柜位选位、SVG）
- 设备管理
- 自动上架（U 位）
- SVG 机柜图
- Dashboard
- Excel / PDF 导入导出
- RBAC 与用户/角色管理 UI

Version 2.0

增加：

- PDU
- UPS
- 配线管理
- CMDB
- LDAP
- Webhook

Version 3.0

增加：

- AI助手
- AI容量预测
- AI自动布局
- Digital Twin

---

# 4 Product Scope

## Included

- Rack Management
- Device Management
- Room Management
- Dashboard
- SVG Engine
- Layout Engine
- User Management
- Role Management
- Import & Export
- Audit Log

## Excluded

V1 不包括：

- 实时监控
- 温湿度采集
- 自动控制UPS
- 自动控制PDU
- 视频监控

---

# 5 Technology Stack

## Backend

Python 3.12

FastAPI

SQLAlchemy

Alembic

Pydantic v2

Celery

Redis

---

## Frontend

Vue3

TypeScript

Vite

Pinia

Element Plus

SVG

ECharts

---

## Database

Development

SQLite

Production

PostgreSQL 16

---

## Deployment

Docker

Docker Compose

Nginx

---

## Authentication

JWT

RBAC

OAuth2（Future）

---

# 6 Repository Structure

```text
rackdcim-pro

backend/

frontend/

deployment/

docs/

tests/

scripts/

.cursor/

.github/

README.md

LICENSE
```

---

# 7 Documentation Structure

```text
docs

00-Project.md

01-PRD.md

02-System-Architecture.md

03-Domain-Model.md

04-Database-Design.md

05-API-Design.md

06-Frontend-Design.md

07-Backend-Design.md

08-Layout-Engine.md

09-SVG-Engine.md

10-AI-Platform.md

11-Security.md

12-Deployment.md

13-Test-Plan.md

14-Roadmap.md（内容为运维操作指南 Operations Guide）
```

所有开发均以 docs 为唯一事实来源（Single Source of Truth）。文档版本 **1.1.0** 起与 V1 实现（机房布局/编号、导入导出、RBAC UI）对齐。

---

# 8 Development Workflow

项目采用 Documentation Driven Development（DDD）。

开发流程如下：

Project

↓

PRD

↓

Architecture

↓

Database

↓

API

↓

Backend

↓

Frontend

↓

Algorithm

↓

Testing

↓

Release

任何代码开发必须基于对应文档。

---

# 9 Coding Standards

## Python

- Python 3.12
- PEP8
- Type Hint
- Black
- Ruff

## Frontend

- Vue3
- Composition API
- TypeScript
- ESLint
- Prettier

## API

- RESTful
- OpenAPI 3.1
- JSON Response
- Versioning

## Database

- Snake Case
- Primary Key：UUID
- Foreign Key
- Soft Delete
- Audit Fields

---

# 10 Version Strategy

采用 Semantic Versioning。

格式：

MAJOR.MINOR.PATCH

例如：

1.0.0

1.1.0

2.0.0

---

# 11 Branch Strategy

Git Flow

main

release

develop

feature/*

bugfix/*

hotfix/*

---

# 12 Milestones

| Milestone | Description            | V1 状态 |
| --------- | ---------------------- | ------- |
| M1        | Project Initialization | Done    |
| M2        | PRD                    | Done    |
| M3        | Architecture           | Done    |
| M4        | Database               | Done（含 room 布局迁移 0003–0005） |
| M5        | Backend                | Done（quick room、export、users） |
| M6        | Frontend               | Done（Room/Rack/Users/Roles） |
| M7        | Layout Engine          | Partial（U 位 + Room 编号） |
| M8        | SVG Engine             | Partial（机柜 SVG） |
| M9        | Testing                | In progress |
| M10       | Release                | Pending |

---

# 13 Future Planning

未来计划增加：

- AI Assistant
- CMDB
- IPAM
- Cable Management
- Power Management
- Network Topology
- Monitoring Integration
- Digital Twin

---

# 14 License

推荐采用：

Apache License 2.0

理由：

- 商业友好
- 支持闭源商业发行
- 社区成熟
- 企业接受度高

---

# References

- docs/01-PRD.md
- docs/02-System-Architecture.md
- docs/03-Domain-Model.md
- docs/04-Database-Design.md

---

# Approval

| Role               | Name | Status  |
| ------------------ | ---- | ------- |
| Product Owner      | Enzo | Pending |
| Solution Architect | TBD  | Pending |
| Technical Lead     | TBD  | Pending |

---