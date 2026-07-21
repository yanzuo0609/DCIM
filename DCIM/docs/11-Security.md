---
title: Security Architecture Specification
project: RackDCIM Pro
version: 1.0.0
status: Draft
author: Enzo
date: 2026-07-17
category: Security
classification: Internal
---

# Security Architecture Specification

> RackDCIM Pro
>
> Enterprise Security Architecture

---

# Revision History

| Version | Date       | Author | Description     |
| ------- | ---------- | ------ | --------------- |
| 1.0.0   | 2026-07-17 | Enzo   | Initial Version |
| 1.1.0   | 2026-07-17 | Enzo   | Sync V1 permission codes and default admin |

---

# Table of Contents

1. Security Overview
2. Security Objectives
3. Security Architecture
4. Authentication
5. Authorization
6. Password Security
7. Session & Token Security
8. API Security
9. Data Security
10. Database Security
11. File Security
12. Audit & Logging
13. AI Security
14. Network Security
15. Deployment Security
16. Compliance
17. Incident Response
18. Security Checklist

---

# 1. Security Overview

RackDCIM Pro 采用“纵深防御（Defense in Depth）”安全模型。

安全控制覆盖：

- 身份认证
- 权限控制
- 数据保护
- API 防护
- 文件安全
- AI 安全
- 审计追踪
- 部署安全

目标：

- 机密性（Confidentiality）
- 完整性（Integrity）
- 可用性（Availability）
- 可审计性（Auditability）

---

# 2. Security Objectives

必须满足：

✓ 所有接口鉴权

✓ 最小权限原则

✓ 敏感数据加密

✓ 全量审计日志

✓ 防止越权访问

✓ 防止注入攻击

✓ 防止 Prompt Injection

✓ 支持企业合规

---

# 3. Security Architecture

```text
User
  │
  ▼
HTTPS
  │
  ▼
Nginx/WAF
  │
  ▼
FastAPI Gateway
  │
  ├── JWT Authentication
  ├── RBAC Authorization
  ├── Rate Limiter
  ├── Audit Middleware
  └── Input Validation
  │
  ▼
Business Services
  │
  ▼
PostgreSQL / Redis / MinIO
```

---

# 4. Authentication

采用：

- JWT Access Token
- Refresh Token

Access Token：

- 有效期：15 分钟
- 用于 API 调用

Refresh Token：

- 有效期：7 天
- 用于刷新 Access Token

Header：

```http
Authorization: Bearer <token>
```

---

## 4.1 Login Security

登录必须：

- BCrypt 哈希
- 登录失败计数
- 账户锁定
- IP 记录
- MFA 预留

账户锁定：

| 条件           | 动作         |
| -------------- | ------------ |
| 连续失败 5 次  | 锁定 15 分钟 |
| 连续失败 10 次 | 锁定 1 小时  |

---

# 5. Authorization

采用 RBAC。

权限模型：

```text
User
  ↓
Role
  ↓
Permission
```

权限粒度（种子 `DEFAULT_PERMISSIONS`）：

```text
admin:*
datacenter:view|create|update|delete
rack:view|create|update|delete
device:view|create|update|delete
device:import
device:export
audit:view
dashboard:view
user:view|create|update|delete
role:view|create|update|delete
```

规则：

- 默认拒绝（Deny by Default）
- 用户持有 `admin:*` 时，`require_permissions` 全部放行
- 不可删除用户名 `admin`；不可删除角色 `code=admin`
- 不可通过 API 修改 admin 角色的 `permission_ids`
- 后续启动由 `ensure_permissions` 将缺失权限补齐到 admin 角色

### 默认管理员（仅空库首次种子）

| Field | Value |
| ----- | ----- |
| username | `admin` |
| password | `Admin@12345678` |
| email | `admin@rackdcim.example.com` |
| role | `admin`（全部权限） |

生产环境发布前必须修改密码；见清单「默认账号密码已修改」。

---

# 6. Password Security

密码要求：

- 最少 12 位
- 必须包含大小写
- 必须包含数字
- 必须包含特殊字符

存储：

```text
BCrypt
Cost Factor: 12
```

禁止：

- 明文存储
- 可逆加密
- SHA1/MD5

---

# 7. Session & Token Security

Token 必须：

- 使用 HS256/RS256
- 包含 exp
- 包含 jti
- 包含 user_id
- 包含 role

支持：

- Token Blacklist
- 强制注销
- 密码修改后失效

---

# 8. API Security

## 8.1 Input Validation

所有输入必须：

- 类型校验
- 长度校验
- 枚举校验
- UUID 校验
- 文件类型校验

禁止直接拼接 SQL。

统一使用 ORM 或参数化查询。

---

## 8.2 Rate Limiting

默认：

```text
100 req/min
```

登录：

```text
10 req/min
```

AI 接口：

```text
20 req/min
```

导入接口：

```text
5 req/min
```

---

## 8.3 CORS

仅允许配置白名单：

```text
https://dcim.example.com
https://admin.example.com
```

禁止：

```text
*
```

---

# 9. Data Security

敏感字段：

- serial_number
- ip_address
- purchase_price
- vendor_contract
- access_token

保护方式：

- 静态加密（AES-256）
- 传输加密（TLS 1.3）
- 日志脱敏

---

# 10. Database Security

数据库账户：

- app_user（业务）
- migration_user（迁移）
- readonly_user（只读）

原则：

- 最小权限
- 禁止使用 superuser
- 禁止共享账号

---

## 10.1 Backup Security

备份必须：

- 加密
- 校验
- 异地保存
- 定期恢复演练

---

# 11. File Security

上传文件：

支持：

- .xlsx
- .csv
- .pdf
- .svg

必须：

- MIME 校验
- 扩展名校验
- 大小限制
- 病毒扫描
- 随机文件名

默认限制：

```text
100 MB
```

---

# 12. Audit & Logging

必须记录：

- 登录
- 登出
- 新增
- 修改
- 删除
- 导入
- 导出
- 权限变更
- AI 操作

日志字段：

```text
timestamp
user_id
ip
action
resource
result
request_id
```

日志保留：

```text
≥ 180 days
```

---

# 13. AI Security

AI 是高风险模块。

必须：

- Tool 权限校验
- Prompt Injection 防护
- 敏感信息过滤
- 输出校验
- 操作确认机制

禁止 AI：

- 未授权删除数据
- 未授权修改配置
- 越权查询资产
- 执行系统命令

---

## 13.1 Prompt Injection Defense

检查：

- ignore previous instructions
- reveal secrets
- dump database
- system prompt
- token

发现后：

```text
BLOCK + AUDIT
```

---

# 14. Network Security

要求：

- TLS 1.3
- HSTS
- Secure Cookie
- X-Frame-Options
- CSP
- X-Content-Type-Options

管理端口仅允许内网访问。

---

# 15. Deployment Security

Docker：

- 非 root 用户
- 只读文件系统（可选）
- 最小镜像
- 定期漏洞扫描

Kubernetes：

- NetworkPolicy
- PodSecurity
- Secret 管理
- 镜像签名

---

# 16. Compliance

参考：

- ISO 27001
- SOC 2
- NIST CSF
- OWASP ASVS
- OWASP Top 10

---

# 17. Incident Response

流程：

```text
Detect
  ↓
Contain
  ↓
Investigate
  ↓
Eradicate
  ↓
Recover
  ↓
Review
```

严重事件：

- 数据泄露
- 权限绕过
- RCE
- 供应链攻击
- AI 越权执行

必须在 24 小时内完成初步分析。

---

# 18. Security Checklist

发布前必须确认：

- [ ] HTTPS 已启用
- [ ] JWT 密钥已更换
- [ ] 默认管理员密码已修改（勿使用 `Admin@12345678`）
- [ ] 数据库密码已修改
- [ ] CORS 已配置
- [ ] Rate Limit 已启用
- [ ] 审计日志正常
- [ ] 备份已验证
- [ ] 漏洞扫描通过
- [ ] AI 安全规则已启用（启用 AI 模块时）

---

# References

- docs/02-System-Architecture.md
- docs/05-API-Design.md
- docs/07-Backend-Design.md
- docs/10-AI-Platform.md

---