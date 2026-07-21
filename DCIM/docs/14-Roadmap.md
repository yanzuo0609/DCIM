---
title: Operations Guide
project: RackDCIM Pro
version: 1.0.0
status: Draft
author: Enzo
date: 2026-07-17
category: Operations
---

# Operations Guide

> RackDCIM Pro
>
> Installation, Operations and Maintenance Guide

---

# Revision History

| Version | Date       | Author | Description     |
| ------- | ---------- | ------ | --------------- |
| 1.0.0   | 2026-07-17 | Enzo   | Initial Version |
| 1.1.0   | 2026-07-17 | Enzo   | Sync V1 ops: seed admin, room quick, import/export |

---

# Table of Contents

1. Guide Overview
2. Deployment Requirements
3. Installation
4. System Initialization
5. User Management
6. Infrastructure Management
7. Rack Management
8. Device Management
9. Layout Operations
10. SVG Visualization
11. AI Assistant
12. System Maintenance
13. Backup & Recovery
14. Troubleshooting
15. Daily Operations Checklist

---

# 1 Guide Overview

本文档用于指导：

- 系统安装
- 系统配置
- 日常使用
- 运维管理
- 故障处理
- 升级维护

适用于：

- 系统管理员
- 运维工程师
- 数据中心管理员
- 技术支持人员

---

# 2 Deployment Requirements

## Hardware

| Component | Minimum    | Recommended |
| --------- | ---------- | ----------- |
| CPU       | 4 Core     | 16 Core     |
| Memory    | 8 GB       | 32 GB       |
| Disk      | 100 GB SSD | 1 TB SSD    |
| Network   | 1 Gbps     | 10 Gbps     |

---

## Software

- Ubuntu 24.04 LTS
- Docker
- Docker Compose
- PostgreSQL 16
- Redis 7
- MinIO
- Python 3.12

---

# 3 Installation

## 3.1 本地开发（当前默认）

```
# Backend
cd backend
# 配置 .env（参考 .env.example），默认 SQLite
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev   # http://localhost:5173，代理 /api → 8000
```

首次启动空库会自动建表、补齐 room 列（SQLite）、并种子默认管理员。

默认登录：`admin` / `Admin@12345678`（生产必须修改）。

## 3.2 Docker / 服务器安装

```
准备服务器 → 安装 Docker → 配置 .env → docker compose up -d
→ Alembic 迁移 → 验证登录
```

验证：打开前端 → Login → Dashboard。

---

# 4 System Initialization

种子（`app/core/seed.py`）在无用户时创建：

| Item | Value |
| ---- | ----- |
| 管理员 | `admin` / `Admin@12345678` |
| 角色 | `admin`（全部权限） |
| 机柜模板 | STD-42U、STD-48U |
| 样例型号 | DELL R750-2U、HPE SW-1U |

首次登录后建议：

- 修改管理员密码
- 创建数据中心（含地理位置）
- 在机房页快速创建机房（楼号 / 编号 / 布局 / 编号规则）
- 按机柜位创建机柜并上架设备
- 按需创建业务角色与用户

---

# 5 User Management

V1 UI：`/system/users`、`/system/roles`。

支持：

- 新建 / 修改 / 禁用 / 删除用户（不可删 `admin`）
- 多角色绑定
- 角色权限多选（不可删 `admin` 角色，不可清空其权限）

权限模型：RBAC，见 `docs/11-Security.md`。

预置角色仅种子 `admin`；Operator / Auditor / Viewer 可按需自建。

---

# 6 Infrastructure Management

推荐路径（V1）：

```
Data Center（含 location）
        ↓
Room Quick Create（building_no + room_no + layout + slot codes）
        ↓
自动创建 Building / 默认 Floor「1F」
        ↓
Rack（选机房空闲机柜位）
```

机房布局：

- auto：`rack_rows × rack_columns`
- manual：`row_layout` 每排不等数量
- 编号 auto（前缀 `A` 或 `A-D`）/ custom（`slot_codes`）

创建后可用「布局图」查看机柜位占用。

---

# 7 Rack Management

创建：

```
选择机房 → 选择空闲机柜位（带 slot code）
→ 模板 STD-42U / STD-48U / 自定义 U
→ 确认 code/name → 保存
```

支持：机柜 SVG 预览、U 位布局上架。批量机柜 Excel 导入为后续增强。

---

# 8 Device Management

支持：

- 设备 CRUD
- 上架到机柜 U 位
- Excel / PDF 导出（`device:export`）
- Excel 导入与模板下载（`device:import`）

导入必填：hostname、serial_number、model_code。

---

# 9 Layout Operations

流程：

```
导入设备

↓

自动布局

↓

冲突检测

↓

生成布局

↓

保存

↓

SVG生成
```

支持：

- 自动布局
- 手工调整
- 回滚
- 布局预览

---

# 10 SVG Visualization

功能：

- 查看机柜
- 缩放
- 拖拽
- 搜索设备
- 导出 SVG
- 导出 PNG
- 导出 PDF

支持：

- 前视图
- 后视图
- 全屏模式

---

# 11 AI Assistant

支持：

- 自然语言查询
- 设备定位
- 容量分析
- 自动生成报表
- 布局建议
- 运维问答

示例：

```
哪些机柜剩余空间超过20U？

GPU服务器分布在哪里？

生成本月容量报告。
```

---

# 12 System Maintenance

定期检查：

- CPU
- Memory
- Disk
- Database
- Redis
- MinIO

建议：

每天：

```
Dashboard

↓

Health Check

↓

Logs

↓

Backup
```

每周：

- 更新镜像
- 检查告警
- 清理日志

---

# 13 Backup & Recovery

备份：

```
Database

↓

MinIO

↓

Configuration

↓

Logs
```

恢复流程：

```
停止服务

↓

恢复数据库

↓

恢复文件

↓

启动服务

↓

校验
```

建议：

每日自动备份。

---

# 14 Troubleshooting

## 无法登录

检查：

- 用户状态
- JWT
- 数据库连接
- Redis

---

## SVG 无法显示

检查：

- Layout 数据
- SVG Engine
- 浏览器缓存

---

## Excel 导入失败

检查：

- 模板
- 字段映射
- 重复数据
- 编码格式

---

## AI 无响应

检查：

- API Key
- 模型连接
- Token 配额
- 日志

---

# 15 Daily Operations Checklist

## 每日

- 登录 Dashboard
- 检查系统状态
- 查看告警
- 检查备份
- 检查日志

---

## 每周

- 清理历史日志
- 检查数据库容量
- 检查 Redis
- 检查 MinIO
- 更新系统补丁

---

## 每月

- 全量备份验证
- 权限审计
- 用户清理
- 性能分析
- 容量规划

---

# Appendix A

## 系统健康检查

| 检查项     | 状态 |
| ---------- | ---- |
| API        | ✓    |
| Database   | ✓    |
| Redis      | ✓    |
| MinIO      | ✓    |
| AI Gateway | ✓    |
| Celery     | ✓    |

---

# Appendix B

## 运维联系人

| Role             | Responsibility |
| ---------------- | -------------- |
| System Admin     | 平台管理       |
| DBA              | 数据库维护     |
| Network Admin    | 网络保障       |
| Security Admin   | 安全审计       |
| Support Engineer | 故障处理       |

---

# Appendix C

## 常用命令

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f backend

# 重启服务
docker compose restart

# 数据库迁移
alembic upgrade head

# 备份数据库
pg_dump rackdcim > backup.sql

# 恢复数据库
psql rackdcim < backup.sql
```

---

# References

- docs/12-Deployment.md
- docs/13-Test-Plan.md
- docs/11-Security.md
- docs/07-Backend-Design.md
- docs/05-API-Design.md
- docs/03-Domain-Model.md

---

# Appendix D - V1 Implementation Status

| Capability | Status |
| ---- | ---- |
| Local SQLite + seed admin | Done |
| Room quick create / layout / codes / floorplan | Done |
| Rack templates and slot picker | Done |
| Device import/export | Done |
| User / Role UI | Done |
| Docker production compose | Planned (see 12-Deployment) |
| AI Assistant | Planned (see 10-AI-Platform) |

See milestones in docs/00-Project.md section 12.

---
