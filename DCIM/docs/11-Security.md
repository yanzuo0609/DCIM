---
title: Security Architecture Specification
project: RackDCIM Pro
version: 1.3.0
status: Active
author: Enzo
date: 2026-07-22
last_code_sync: 2026-07-22
category: Security
classification: Internal
---

# Security Architecture Specification

> Defense in depth — JWT + RBAC + bcrypt + audit API

---

## Revision History

| Version | Date | Author | Description |
| ------- | ---- | ------ | ----------- |
| 1.3.0 | 2026-07-22 | Enzo | V1 implemented vs planned controls |

---

## 1. Security Objectives

| Objective | V1 Status |
| --------- | --------- |
| Authenticate all API calls (except health/login) | ✅ |
| Least privilege RBAC | ✅ |
| Secure password storage | ✅ bcrypt |
| Input validation | ✅ Pydantic |
| Audit trail API | ✅ |
| HTTPS in production | 📋 deploy responsibility |
| Rate limiting | 📋 |
| MFA | 📋 |

---

## 2. Architecture

```text
Client
  → HTTPS (production)
  → FastAPI
       ├── CORS middleware (whitelist)
       ├── JWT validation (get_current_user)
       ├── RBAC (require_permissions)
       ├── Pydantic validation
       └── Exception handlers (no stack leak in prod)
  → PostgreSQL / SQLite
```

---

## 3. Authentication

### 3.1 JWT Configuration

| Token | TTL | Config Key |
| ----- | --- | ---------- |
| Access | 15 min | ACCESS_TOKEN_EXPIRE_MINUTES |
| Refresh | 7 days | REFRESH_TOKEN_EXPIRE_DAYS |
| Algorithm | HS256 | JWT_ALGORITHM |
| Secret | env | SECRET_KEY |

Header:

```http
Authorization: Bearer <access_token>
```

Implementation: `app/core/security.py`, `app/services/auth.py`.

### 3.2 Login Flow

1. POST `/auth/login` with username/password
2. Verify bcrypt hash
3. Increment `failed_login_count` on failure; set `locked_until` per policy fields
4. Return access + refresh tokens
5. Frontend stores in localStorage; attaches to requests

### 3.3 Token Refresh

Frontend interceptor (`api/index.ts`) calls `/auth/refresh` on 401, retries once.

---

## 4. Authorization (RBAC)

### 4.1 Model

```text
User ──M:N── Role ──M:N── Permission
```

### 4.2 Permission Catalog

| Code | Description |
| ---- | ----------- |
| admin:* | Full access (bypass) |
| datacenter:view\|create\|update\|delete | Infrastructure |
| rack:view\|create\|update\|delete | Racks & templates |
| device:view\|create\|update\|delete | Devices, IP, contracts |
| device:import | Excel import |
| device:export | Excel/PDF export |
| dashboard:view | Dashboard |
| audit:view | Audit logs |
| user:view\|create\|update\|delete | User admin |
| role:view\|create\|update\|delete | Role admin |

Source: `DEFAULT_PERMISSIONS` in `core/seed.py`.

### 4.3 Protected Resources

| Resource | Rule |
| -------- | ---- |
| User `admin` | Cannot delete |
| Role `admin` | Cannot delete; cannot modify permission_ids via API |
| System device types | Cannot delete if is_system |

Enforcement: `UserMgmtService`, `DeviceService`, `require_permissions`.

---

## 5. Password Policy

| Rule | Enforcement |
| ---- | ----------- |
| Minimum 12 characters | API schema validation |
| Storage | bcrypt hash only |
| Default seed password | `Admin@12345678` — **must change in production** |

Recommended production policy (📋 not all enforced in code):

- Mixed case, digit, special character
- Rotation on compromise

---

## 6. API Security

### 6.1 Input Validation ✅

- Pydantic models on all request bodies
- UUID format validation
- Enum constraints on status fields
- File upload: extension + size checks on import endpoints

### 6.2 SQL Injection ✅

- SQLAlchemy ORM / parameterized queries only
- No raw SQL string concatenation in services

### 6.3 CORS ✅

`CORS_ORIGINS` in settings — default localhost dev origins. Production must set explicit domains; never `*`.

### 6.4 Rate Limiting 📋

Planned limits documented in [05-API-Design.md](05-API-Design.md). Not implemented in middleware.

---

## 7. Data Security

| Data | Protection |
| ---- | ---------- |
| password_hash | bcrypt |
| JWT secret | env var, not in git |
| Profile credentials (BMC) | `credential_crypto.py` encryption helper |
| serial_number, IP | Access controlled by RBAC |
| Logs | Avoid password/token in log output |

---

## 8. Audit & Logging

### 8.1 Audit API ✅

```http
GET /api/v1/audit/logs?page=1&page_size=20
```

Permission: `audit:view`.

### 8.2 Planned Audit Events

Login, logout, CRUD, import/export, permission changes, future AI actions.

Retention target: ≥180 days (operational policy).

---

## 9. File Upload Security

Import endpoints accept `.xlsx`:

| Control | Status |
| ------- | ------ |
| MIME / extension check | ✅ basic |
| Size limit | ✅ service-level |
| Virus scan | 📋 |
| Random storage name | N/A (in-memory parse) |

---

## 10. Deployment Security

| Control | Docker | Production checklist |
| ------- | ------ | -------------------- |
| Non-root container | 📋 partial | Review Dockerfiles |
| SECRET_KEY rotation | — | Required |
| HTTPS termination | nginx | Required |
| DB credentials | compose env | Change defaults |

---

## 11. AI Security 📋

When AI module is implemented (see [10-AI-Platform.md](10-AI-Platform.md)):

- Tool calls inherit user RBAC
- Prompt injection filtering
- Human confirmation for write/delete tools
- Full audit of AI actions

---

## 12. Pre-Release Checklist

- [ ] HTTPS enabled
- [ ] SECRET_KEY changed from default
- [ ] Admin password changed from `Admin@12345678`
- [ ] PostgreSQL credentials rotated
- [ ] CORS restricted to production domain
- [ ] `.env` not committed
- [ ] Backup verified
- [ ] Dependency scan (pip-audit / npm audit)

---

## References

- [05-API-Design.md](05-API-Design.md)
- [07-Backend-Design.md](07-Backend-Design.md)
- [12-Deployment.md](12-Deployment.md)
