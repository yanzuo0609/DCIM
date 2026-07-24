# RackDCIM Pro — Postman Collection

与 OpenAPI `/api/v1/openapi.json` 同步的 API 测试套件。

## 文件

| 文件 | 说明 |
| ---- | ---- |
| `RackDCIM-Pro.postman_collection.json` | 请求集合（含 Auth 自动存 Token） |
| `RackDCIM-Pro.postman_environment.json` | 本地开发环境变量 |

## 快速开始

### 1. 启动后端

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

确认：http://localhost:8000/health

### 2. 导入 Postman

1. 打开 Postman → **Import**
2. 拖入本目录两个 JSON 文件
3. 右上角 Environment 选择 **RackDCIM Pro - Local**

### 3. 获取 Token

1. 打开 **Auth → Login**
2. 默认 body 使用种子账号 `admin` / `Admin@12345678`
3. 点击 **Send**
4. Tests 脚本会自动写入 `access_token` 和 `refresh_token`

后续请求使用 Collection 级 Bearer `{{access_token}}`。

### 4. 推荐调用顺序（冒烟测试）

```text
Auth → Login
Infrastructure → Create Datacenter      (保存 datacenter_id)
Infrastructure → Quick Create Room      (保存 room_id)
Racks → Create Rack                     (保存 rack_id)
Devices → List Device Models            (复制 model id 到 Create Device body)
Devices → Create Device                 (保存 device_id)
Layout → Mount Device
Racks → Get Rack SVG
Dashboard → Summary
```

## 环境变量

| 变量 | 说明 | 填充方式 |
| ---- | ---- | -------- |
| `base_url` | API 根路径 | 默认 `http://localhost:8000/api/v1` |
| `access_token` | JWT | Login 自动 |
| `refresh_token` | 刷新令牌 | Login 自动 |
| `datacenter_id` | 数据中心 ID | Create Datacenter 自动 |
| `room_id` | 机房 ID | Quick Create Room 自动 |
| `rack_id` | 机柜 ID | Create Rack 自动 |
| `device_id` | 设备 ID | Create Device 自动 |
| `contract_id` | 合同 ID | Create Contract 自动 |
| `ip_id` | IP 记录 ID | Create IP Address 自动 |

Docker 部署时将 `base_url` 改为 `http://localhost/api/v1`（经 nginx 反代）。

## 与 OpenAPI 同步

### 方式 A：从运行中的服务导入（推荐）

1. Postman → Import → Link
2. 输入：`http://localhost:8000/api/v1/openapi.json`
3. 生成新 Collection 后与本文档 §10 示例对照

OpenAPI 为**权威来源**；本 Collection 为常用流程的手工 curated 子集。

### 方式 B：手工维护

API 变更时需同步更新：

1. `backend/app/schemas/` — Pydantic 模型
2. `docs/05-API-Design.md` §10 — JSON 示例
3. 本目录 Collection JSON — 请求 body

### 校验清单

- [ ] 新增 POST/PUT 在 OpenAPI `/docs` 可见
- [ ] `05-API-Design.md` §10 有对应示例
- [ ] Postman Collection 含至少一条冒烟请求
- [ ] Login 脚本仍能写入 token

## Newman CLI（可选）

```bash
npm install -g newman

newman run docs/postman/RackDCIM-Pro.postman_collection.json \
  -e docs/postman/RackDCIM-Pro.postman_environment.json \
  --folder "Auth" \
  --folder "Health"
```

完整冒烟需先手动或通过脚本填充 `device_model_id` 等依赖 ID。

## 参考

- [05-API-Design.md](../05-API-Design.md) — 完整 API 规范与 JSON 示例
- Swagger UI：http://localhost:8000/api/v1/docs
