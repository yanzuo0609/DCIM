---
title: System Architecture Design
project: RackDCIM Pro
version: 1.0.0
status: Draft
author: Enzo
date: 2026-07-16
category: Architecture
---

# System Architecture Design

> RackDCIM Pro  
> AI Native Data Center Infrastructure Management Platform

---

# Revision History

| Version | Date       | Author | Description     |
| ------- | ---------- | ------ | --------------- |
| 1.0.0   | 2026-07-16 | Enzo   | Initial Version |
| 1.1.0   | 2026-07-17 | Enzo   | Sync V1 modules: room layout, export, RBAC |

---

# Table of Contents

1. Architecture Overview
2. Design Principles
3. Overall Architecture
4. Layered Architecture
5. System Modules
6. Technical Stack
7. Core Business Flow
8. Module Dependencies
9. High Availability
10. Security Architecture
11. Scalability
12. Deployment Architecture
13. Performance Design
14. Future Evolution

---

# 1. Architecture Overview

RackDCIM Pro 采用现代企业级三层架构，并遵循 **API First、DDD（Domain Driven Design）** 和 **Documentation Driven Development（DDDoc）** 的设计理念。

系统目标：

- 高内聚、低耦合
- 模块化
- 插件化
- 云原生
- AI Ready
- 支持私有化部署

---

# 2. Design Principles

## 2.1 API First

所有业务能力均通过 REST API 对外提供。

前端、AI、第三方系统均通过统一 API 调用。

---

## 2.2 Domain Driven Design

系统按照业务领域划分，而不是按照数据库划分。

例如：

- Rack Domain
- Device Domain
- User Domain
- Layout Domain
- Dashboard Domain

---

## 2.3 Configuration First

所有业务规则均可配置：

- Rack 模板
- U 位规则
- 颜色
- 编号规则
- 自动布局策略

---

## 2.4 AI Native

所有业务数据支持：

- AI Assistant
- RAG
- Capacity Prediction
- Smart Layout

---

# 3. Overall Architecture

```

┌──────────────────────────────────────────────┐
│                 Browser                      │
└──────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│          Vue3 + Element Plus + SVG           │
└──────────────────────────────────────────────┘
                     │
               REST API
                     │
                     ▼
┌──────────────────────────────────────────────┐
│                 FastAPI                      │
├──────────────────────────────────────────────┤
│ Authentication                               │
│ User                                         │
│ Rack                                         │
│ Device                                       │
│ Layout                                       │
│ Dashboard                                    │
│ AI Engine                                    │
└──────────────────────────────────────────────┘
                     │
      ┌──────────────┴──────────────┐
      ▼                             ▼
 PostgreSQL                      Redis
      │                             │
      ▼                             ▼
   MinIO                       Celery

```

---

# 4. Layered Architecture

## Presentation Layer

负责：

- Vue3 页面
- SVG 图形
- Dashboard
- 登录
- 权限

---

## API Layer

FastAPI

负责：

- REST API
- JWT
- Swagger
- 参数验证

---

## Service Layer

负责：

- 业务逻辑
- 权限校验
- 数据转换
- 调用算法

---

## Domain Layer

负责：

- Rack
- Device
- User
- Room
- Dashboard

所有业务规则均位于此层。

---

## Infrastructure Layer

负责：

- PostgreSQL
- Redis
- MinIO
- 日志
- 文件上传
- 第三方接口

---

# 5. System Modules

## Infrastructure

- Data Center
- Building / Floor（快速创建机房时可自动创建）
- Room（布局、机柜位编号、容量）

## Rack

- Rack Template
- Rack（机柜位绑定）
- Rack Position（U 位）
- SVG 视图

## Device

- Device CRUD
- Import / Export（xlsx / pdf）
- Mount to Rack

## Identity

- User / Role / Permission（RBAC）
- JWT Auth

## Dashboard

- Summary / Utilization / Power / Device Count

## Layout Engine

- 机房机柜位编号
- 自动布局 / U 位计算 / 冲突检测

## SVG Engine

- 机柜 SVG / 导出

## AI Engine（规划）

- AI 问答 / 布局建议 / 容量预测 / RAG

---

# 6. Technology Stack

| Layer     | Technology   |
| --------- | ------------ |
| Frontend  | Vue3 + TS    |
| UI        | Element Plus |
| Chart     | ECharts      |
| Graphics  | SVG          |
| Backend   | FastAPI      |
| ORM       | SQLAlchemy   |
| Migration | Alembic      |
| Database  | PostgreSQL   |
| Cache     | Redis        |
| Task      | Celery       |
| Storage   | MinIO        |
| Container | Docker       |

---

# 7. Core Business Flow

设备导入：

```

Excel

↓

Import Service

↓

Device Validation

↓

Database

↓

Layout Engine

↓

Rack Position

↓

SVG Engine

↓

Dashboard

```

---

# 8. Module Dependencies

```

User
│

├── Permission

├── Audit

└── Login

Rack
│

├── Device

├── Layout

└── Dashboard

Layout
│

├── SVG

└── Dashboard

AI
│

├── Layout

├── Dashboard

└── Device

```

---

# 9. High Availability

支持：

- Docker Compose
- PostgreSQL Backup
- Redis Persistence
- MinIO Replication

未来支持：

- Kubernetes
- PostgreSQL Cluster
- Redis Sentinel

---

# 10. Security Architecture

认证：

JWT

授权：

RBAC

日志：

Audit Log

密码：

BCrypt

接口：

HTTPS

上传：

病毒扫描

---

# 11. Scalability

支持增加：

- CMDB
- IPAM
- Cable
- PDU
- UPS
- Monitoring
- AI Plugin

无需修改核心代码。

---

# 12. Deployment Architecture

```

Internet

↓

Nginx

↓

FastAPI

↓

PostgreSQL

↓

Redis

↓

MinIO

```

支持：

- Linux
- Docker
- Kubernetes

---

# 13. Performance Design

目标：

| Item                | Target |
| ------------------- | ------ |
| API Response        | <200ms |
| SVG Render          | <500ms |
| Dashboard           | <2s    |
| Import 1000 Devices | <10s   |

---

# 14. Future Evolution

未来增加：

- AI Agent
- MCP Server
- Digital Twin
- Graph Database
- Multi Region
- Multi Tenant

---

# References

- 00-Project.md
- 01-PRD.md
- 03-Domain-Model.md
- 04-Database-Design.md

---