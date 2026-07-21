---
title: Deployment Design Specification
project: RackDCIM Pro
version: 1.0.0
status: Draft
author: Enzo
date: 2026-07-17
category: Deployment
---

# Deployment Design Specification

> RackDCIM Pro
>
> Enterprise Deployment Architecture

---

# Revision History

| Version | Date       | Author | Description     |
| ------- | ---------- | ------ | --------------- |
| 1.0.0   | 2026-07-17 | Enzo   | Initial Version |
| 1.1.0   | 2026-07-17 | Enzo   | Sync V1: local SQLite, seed admin, Alembic 0003–0005 |

---

# Table of Contents

1. Deployment Overview
2. Deployment Architecture
3. Runtime Components
4. Network Architecture
5. Environment Design
6. Docker Deployment
7. Docker Compose
8. Kubernetes Deployment
9. High Availability
10. Backup Strategy
11. Monitoring
12. Logging
13. CI/CD
14. Upgrade Strategy
15. Disaster Recovery

---

# 1 Deployment Overview

RackDCIM Pro 支持以下部署方式：

- Docker Compose
- Kubernetes
- 单机部署
- 多节点部署
- 私有云
- 公有云
- 混合云

目标：

- 高可用
- 高性能
- 可扩展
- 易维护

---

# 2 Deployment Architecture

```
                    Internet
                        │
                  Nginx / SLB
                        │
        ┌───────────────┼───────────────┐
        │               │               │
    Frontend       Backend API      AI Gateway
        │               │               │
        └───────────────┼───────────────┘
                        │
                 PostgreSQL
                        │
          ┌─────────────┼─────────────┐
          │             │             │
        Redis         MinIO       Celery Worker
```

---

# 3 Runtime Components

| Component  | Description |
| ---------- | ----------- |
| Nginx      | 反向代理    |
| Frontend   | Vue3 Web    |
| Backend    | FastAPI     |
| PostgreSQL | 业务数据库  |
| Redis      | 缓存        |
| MinIO      | 对象存储    |
| Celery     | 异步任务    |
| Flower     | 任务监控    |
| Prometheus | 指标采集    |
| Grafana    | 监控看板    |

---

# 4 Network Architecture

推荐网络划分：

```
DMZ
│
├── Nginx

Business Zone
│
├── API
├── Worker
├── AI

Database Zone
│
├── PostgreSQL
├── Redis
├── MinIO
```

端口建议：

| Service    | Port |
| ---------- | ---- |
| Nginx      | 443  |
| Frontend   | 80   |
| Backend    | 8000 |
| PostgreSQL | 5432 |
| Redis      | 6379 |
| MinIO      | 9000 |
| Grafana    | 3000 |
| Prometheus | 9090 |

---

# 5 Environment Design

环境划分：

```
Development
Testing
UAT
Production
Disaster Recovery
```

配置管理：

```
.env.dev
.env.test
.env.uat
.env.prod
```

禁止：

- 在代码中硬编码密码
- 提交密钥到 Git

### 本地开发环境（V1 默认）

| Item | Value |
| ---- | ----- |
| Backend | FastAPI，`uvicorn` 端口 8000 |
| Frontend | Vite，端口 5173，代理 `/api` → 8000 |
| Database | SQLite（`DATABASE_URL`）；生产用 PostgreSQL 16 |
| 配置 | `backend/.env`（参考 `.env.example`） |
| 迁移 | 生产用 Alembic；SQLite 开发路径另有 `_ensure_sqlite_room_columns` |
| 种子 | 空库自动创建 `admin` / `Admin@12345678` |

---

# 6 Docker Deployment

镜像划分：

```
rackdcim-frontend
rackdcim-backend
rackdcim-worker
rackdcim-ai
postgres
redis
minio
nginx
```

镜像规范：

- 最小化基础镜像
- 多阶段构建
- 非 root 用户运行
- 固定版本标签

---

# 7 Docker Compose

目录结构：

```
deploy/
├── docker-compose.yml
├── .env
├── nginx/
├── postgres/
├── redis/
├── minio/
└── scripts/
```

启动流程：

```
docker compose pull
docker compose up -d
docker compose ps
```

---

# 8 Kubernetes Deployment

资源：

```
Deployment
StatefulSet
Service
Ingress
ConfigMap
Secret
PersistentVolume
PersistentVolumeClaim
HorizontalPodAutoscaler
```

建议副本：

| Service    | Replicas |
| ---------- | -------- |
| Frontend   | 2        |
| Backend    | 3        |
| Worker     | 2        |
| AI Gateway | 2        |

---

# 9 High Availability

数据库：

- PostgreSQL Primary/Standby
- 自动故障切换

缓存：

- Redis Sentinel

对象存储：

- MinIO Distributed

应用：

- 多实例部署
- 无状态设计
- 会话依赖 JWT

---

# 10 Backup Strategy

备份对象：

- PostgreSQL
- MinIO
- 配置文件
- 日志

备份策略：

| 类型     | 周期   |
| -------- | ------ |
| 全量备份 | 每日   |
| 增量备份 | 每小时 |
| 日志归档 | 实时   |

保留周期：

```
30 Days
```

---

# 11 Monitoring

监控组件：

```
Prometheus

↓

Grafana
```

监控内容：

- CPU
- Memory
- Disk
- API
- Database
- Redis
- Celery
- MinIO
- AI Gateway

关键指标：

- API TPS
- API 延迟
- 错误率
- 任务队列长度
- 数据库连接数

---

# 12 Logging

统一日志：

```
Application Log
Access Log
Audit Log
Security Log
AI Log
```

日志格式：

JSON

推荐方案：

- Loki
- Elasticsearch

---

# 13 CI/CD

推荐流程：

```
Git Commit

↓

GitHub Actions / GitLab CI

↓

Unit Test

↓

Build Image

↓

Security Scan

↓

Push Registry

↓

Deploy

↓

Smoke Test
```

发布策略：

- Rolling Update
- Blue-Green
- Canary

---

# 14 Upgrade Strategy

升级原则：

- 数据库迁移先执行
- 应用无状态滚动升级
- 支持版本回退
- 自动健康检查

升级流程：

```
Backup

↓

Migration

↓

Deploy

↓

Health Check

↓

Release
```

---

# 15 Disaster Recovery

恢复目标：

| 指标 | 目标     |
| ---- | -------- |
| RPO  | ≤15 分钟 |
| RTO  | ≤60 分钟 |

灾备能力：

- 跨机房备份
- 自动恢复脚本
- 数据一致性校验
- 演练机制

---

# Appendix A

## 推荐服务器规格

| Role       |    CPU | Memory |     Disk |
| ---------- | -----: | -----: | -------: |
| Frontend   | 2 Core |   4 GB |    50 GB |
| Backend    | 4 Core |   8 GB |   100 GB |
| Database   | 8 Core |  32 GB | 1 TB SSD |
| Redis      | 2 Core |   8 GB |   100 GB |
| MinIO      | 4 Core |  16 GB |     2 TB |
| AI Gateway | 8 Core |  32 GB |   200 GB |

---

# Appendix B

## 推荐目录结构

```
/opt/rackdcim
├── app
├── config
├── data
├── logs
├── backup
└── scripts
```

---

# References

- docs/07-Backend-Design.md
- docs/11-Security.md
- docs/04-Database-Design.md

---