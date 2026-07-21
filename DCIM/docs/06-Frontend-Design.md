---
title: Frontend Design Specification
project: RackDCIM Pro
version: 1.0.0
status: Draft
author: Enzo
date: 2026-07-16
category: Frontend
tech_stack: Vue3 + TypeScript + Vite + Element Plus
---

# Frontend Design Specification

> RackDCIM Pro  
> Frontend Design Specification (FDS)

---

# Revision History

| Version | Date       | Author | Description     |
| ------- | ---------- | ------ | --------------- |
| 1.0.0   | 2026-07-16 | Enzo   | Initial Version |
| 1.1.0   | 2026-07-17 | Enzo   | Sync V1 routes, Room floorplan, Rack slots, Users/Roles |

---

# Table of Contents

1. Frontend Overview
2. Design Principles
3. Technology Stack
4. Project Structure
5. Routing Design
6. Layout Design
7. Navigation Design
8. Permission Model
9. State Management
10. Page Design
11. Component Design
12. SVG Rack Design
13. Dashboard Design
14. Theme Design
15. Internationalization
16. Performance Optimization

---

# 1. Frontend Overview

RackDCIM Pro 前端采用现代化 SPA（Single Page Application）架构，提供统一的管理界面，实现：

- 数据中心管理
- 机房管理
- 机柜管理
- 设备管理
- 自动布局
- SVG 可视化
- Dashboard
- 用户权限管理

设计目标：

- 高性能
- 高可维护性
- 响应式布局
- 模块化开发
- AI Ready

---

# 2. Design Principles

采用以下设计原则：

- Component First
- Responsive Design
- Reusable Components
- Lazy Loading
- Permission Driven UI
- SVG Native Rendering

所有页面均支持：

- 深色模式
- 国际化
- 响应式布局
- 权限控制

---

# 3. Technology Stack

| Layer           | Technology   |
| --------------- | ------------ |
| Framework       | Vue3         |
| Language        | TypeScript   |
| Build Tool      | Vite         |
| State           | Pinia        |
| Router          | Vue Router   |
| UI              | Element Plus |
| Chart           | ECharts      |
| SVG             | Native SVG   |
| HTTP            | Axios        |
| Form Validation | Element Plus |

---

# 4. Project Structure

```text
frontend/
├── public/
├── src/
│   ├── api/
│   ├── assets/
│   ├── components/
│   ├── composables/
│   ├── layouts/
│   ├── locales/
│   ├── router/
│   ├── stores/
│   ├── styles/
│   ├── utils/
│   ├── views/
│   ├── App.vue
│   └── main.ts
├── package.json
└── vite.config.ts
```

---

# 5. Routing Design

采用 Vue Router。

主要路由：

```
/
├── dashboard
├── datacenter
├── building
├── floor
├── room
├── rack
├── device
├── asset
├── svg
├── reports
├── system
│   ├── user
│   ├── role
│   └── permission
└── settings
```

支持：

- 动态路由
- 路由守卫
- Breadcrumb
- KeepAlive

---

# 6. Layout Design

整体布局：

```
+------------------------------------------------------+
| Header                                               |
+----------------+-------------------------------------+
| Sidebar        | Main Content                        |
|                |                                     |
|                |                                     |
|                |                                     |
+----------------+-------------------------------------+
| Footer                                              |
+------------------------------------------------------+
```

Header：

- Logo
- 搜索
- 消息通知
- 用户菜单
- 主题切换

Sidebar：

- 折叠菜单
- 图标
- 权限过滤

---

# 7. Navigation Design

菜单结构（V1 已实现）：

```
Dashboard

Infrastructure
├── Data Center   → /datacenters
└── Room          → /rooms

Rack              → /racks

Device            → /devices

System
├── User          → /system/users
└── Role          → /system/roles
```

路由与权限（`frontend/src/router/index.ts`）：

| Route | View | meta.permission |
| ----- | ---- | --------------- |
| /login | LoginView | 公开 |
| / | DashboardView | — |
| /datacenters | DatacenterView | datacenter:view |
| /rooms | RoomView | datacenter:view |
| /racks | RackView | rack:view |
| /devices | DeviceView | device:view |
| /system/users | UserView | user:view |
| /system/roles | RoleView | role:view |

守卫：无 Token → `/login`；无权限 → `/`。

---

# 8. Permission Model

前端权限采用 RBAC。

权限控制：

- 页面
- 菜单
- 按钮
- API

示例：

```
admin:*
datacenter:view|create|update|delete
rack:view|create|update|delete
device:view|create|update|delete|import|export
user:view|create|update|delete
role:view|create|update|delete
audit:view
dashboard:view
```

持有 `admin:*` 的用户通过全部前端权限检查。

按钮控制：

```vue
<el-button v-if="hasPermission('rack:create')">
新增机柜
</el-button>
```

---

# 9. State Management

采用 Pinia。

Store 划分：

```
authStore
userStore
menuStore
rackStore
deviceStore
dashboardStore
themeStore
```

原则：

- 页面状态与业务状态分离
- API 数据统一管理
- Token 持久化

---

# 10. Page Design

## V1 已实现页面

| 页面 | 路由 | 功能要点 |
| ---- | ---- | -------- |
| Login | /login | 登录；后端不可达时提示「无法连接后端」而非笼统密码错误 |
| Dashboard | / | 首页统计 |
| DataCenter | /datacenters | 数据中心 CRUD（含地理位置） |
| Room | /rooms | 快速创建 + 布局图 |
| Rack | /racks | 模板/机柜位/SVG/U 位布局 |
| Device | /devices | CRUD + Excel/PDF 导入导出 |
| User | /system/users | 用户与多角色绑定 |
| Role | /system/roles | 角色与权限多选 |

## Room 页（RoomView）

- 新建：选数据中心 → 楼号 / 机房编号 → 布局（auto 行列 / manual 每排数量）→ 编号（auto 前缀或 custom 逐格）
- 调用 `POST /rooms/quick`
- 创建成功后可打开「布局图」抽屉：按 `row_layout` + `slot_codes` 渲染网格，叠加机柜占用与利用率颜色（空闲 / 低 / 中 / 高）

## Rack 页（RackView）

- 模板单选：STD-42U / STD-48U / 自定义 U
- 选机房后列出空闲机柜位；选中后回填 code/name，提交 `row_no`/`column_no`
- 无空闲位时提示先扩展机房布局
- 支持 SVG 预览与 U 位上架抽屉

## Device 页

- 导入/导出按钮分别受 `device:import` / `device:export` 控制

## User / Role 页

- 用户：用户名、邮箱、密码（≥12）、状态、多角色
- 角色：权限多选；admin 角色不可删，且不开放权限清空编辑

规划中（未在 V1 菜单落地）：Building/Floor 独立页、Reports、Settings。

---

# 11. Component Design

公共组件：

```
BaseTable
BaseForm
BaseSearch
BaseDialog
BaseCard
BaseChart
BaseUpload
BasePagination
```

业务组件：

```
RackCard
RackCanvas
RackSVG
DeviceCard
DeviceEditor
LayoutPreview
DashboardWidget
```

组件原则：

- 单一职责
- 可复用
- Props 驱动
- Emits 通信

---

# 12. SVG Rack Design

SVG 采用原生绘制。

一个 Rack：

```
Rack
├── Frame
├── U Slots
├── Device Block
├── Label
└── Status Layer
```

支持：

- 缩放
- 拖拽
- Hover
- Tooltip
- 设备点击
- 多设备显示
- 前后视图切换

颜色规范：

| 状态   | 颜色 |
| ------ | ---- |
| 空闲   | 绿色 |
| 已占用 | 蓝色 |
| 预留   | 黄色 |
| 故障   | 红色 |

---

# 13. Dashboard Design

首页模块：

```
Summary Card

↓

Capacity Chart

↓

Rack Utilization

↓

Power Consumption

↓

Top Device

↓

Recent Activity
```

图表：

- 饼图
- 柱状图
- 折线图
- 仪表盘
- 热力图

---

# 14. Theme Design

支持：

- Light Theme
- Dark Theme

主题变量：

```
Primary Color
Background
Border
Success
Warning
Danger
Info
```

---

# 15. Internationalization

采用 vue-i18n。

默认语言：

- 中文（简体）
- English

目录：

```
locales/
├── zh-CN.json
└── en-US.json
```

---

# 16. Performance Optimization

优化策略：

- 路由懒加载
- 图片懒加载
- SVG 虚拟渲染
- API 缓存
- KeepAlive
- Tree Shaking
- Gzip/Brotli
- HTTP/2

性能目标：

| 指标      | 目标   |
| --------- | ------ |
| 首屏加载  | <2s    |
| 页面切换  | <300ms |
| SVG 渲染  | <500ms |
| Dashboard | <2s    |

---

# References

- docs/01-PRD.md
- docs/02-System-Architecture.md
- docs/05-API-Design.md
- docs/07-Backend-Design.md

---