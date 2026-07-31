---
title: Deployment Design Specification
project: RackDCIM Pro
version: 1.3.0
status: Active
author: Enzo
date: 2026-07-22
last_code_sync: 2026-07-22
category: Deployment
---

# Deployment Design Specification

> Development · Docker Compose · CI/CD

---

## Revision History

| Version | Date | Author | Description |
| ------- | ---- | ------ | ----------- |
| 1.3.0 | 2026-07-22 | Enzo | Complete deploy runbooks, compose spec, CI matrix |

---

## 1. Deployment Modes

| Mode | Use Case | Database | Command |
| ---- | -------- | -------- | ------- |
| Local dev | Daily development | SQLite | `scripts/dev.ps1` or manual |
| Docker Compose | Staging / prod-like | PostgreSQL 16 | `deployment/docker compose up` |
| Kubernetes | 📋 Future scale-out | PostgreSQL HA | — |

---

## 2. Local Development

### 2.1 Prerequisites

| Tool | Version |
| ---- | ------- |
| Python | ≥3.12 |
| Node.js | ≥20 (CI uses 22) |
| npm | ≥10 |

### 2.2 Backend Setup

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env   # if missing
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Startup behavior:

1. `init_db()` — create tables + SQLite patches
2. `seed_defaults()` — admin user if empty

### 2.3 Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Vite proxy (`vite.config.ts`):

| Path | Target |
| ---- | ------ |
| /api | http://localhost:8000 |
| /health | http://localhost:8000 |

### 2.4 Windows Script

```powershell
.\scripts\dev.ps1
```

Starts backend (uvicorn) + frontend (vite) in separate processes.

### 2.5 Default Credentials

| User | Password | Action |
| ---- | -------- | ------ |
| admin | Admin@12345678 | Change before any shared deploy |

---

## 3. Docker Compose

### 3.1 File Layout

```text
deployment/
├── docker-compose.yml
├── Dockerfile.backend      # Python 3.12-slim
├── Dockerfile.frontend     # Node 22 build → nginx:alpine
└── nginx/default.conf
```

### 3.2 Services

| Service | Image / Build | Ports | Depends On |
| ------- | ------------- | ----- | ---------- |
| postgres | postgres:16-alpine | 5432 | — |
| redis | redis:7-alpine | 6379 | — |
| backend | Dockerfile.backend | 8000 | postgres, redis healthy |
| frontend | Dockerfile.frontend | 80 | backend |

### 3.3 Backend Environment (compose)

```yaml
DATABASE_URL: postgresql+asyncpg://rackdcim:rackdcim@postgres:5432/rackdcim
REDIS_URL: redis://redis:6379/0
CELERY_BROKER_URL: redis://redis:6379/1
SECRET_KEY: change-me-in-production
DEBUG: "false"
```

### 3.4 Nginx Routing

| Location | Upstream |
| -------- | -------- |
| / | SPA static (try_files → index.html) |
| /api/ | backend:8000 |
| /health | backend:8000 |

### 3.5 Deploy Commands

```bash
cd deployment
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

Access:

| Service | URL |
| ------- | --- |
| Frontend | http://localhost |
| Backend API | http://localhost:8000 (direct) or via /api |
| OpenAPI | http://localhost:8000/api/v1/docs |

### 3.6 Gaps in Current Compose

| Item | Status | Recommendation |
| ---- | ------ | -------------- |
| Alembic migration step | ❌ | Add init container or entrypoint script |
| Celery worker | ❌ | Add when async tasks exist |
| MinIO | ❌ | V2 |
| Health check on backend | 🚧 | Add HEALTHCHECK instruction |
| TLS | ❌ | Terminate at reverse proxy |

---

## 4. Production Hardening

### 4.1 Environment Checklist

- [ ] `SECRET_KEY` — cryptographically random
- [ ] `DEBUG=false`
- [ ] PostgreSQL strong password
- [ ] CORS_ORIGINS — production domain only
- [ ] HTTPS via nginx/traefik
- [ ] Admin password changed

### 4.2 Database Migration

```bash
cd backend
alembic upgrade head
```

Do **not** rely on SQLite `create_all` patches in production.

### 4.3 Recommended Server Specs (Single Node)

| Role | CPU | RAM | Disk |
| ---- | --- | --- | ---- |
| All-in-one | 4 core | 8 GB | 100 GB SSD |
| DB dedicated | 8 core | 32 GB | 500 GB SSD |

---

## 5. CI/CD

### 5.1 GitHub Actions (`.github/workflows/ci.yml`)

**Trigger:** push/PR to `main`, `develop`

| Job | Steps | Working Dir |
| --- | ----- | ----------- |
| backend | checkout → Python 3.12 → pip install → black --check → ruff → pytest unit | backend |
| frontend | checkout → Node 22 → npm ci → npm run build | frontend |

### 5.2 CI Gaps

| Check | Status |
| ----- | ------ |
| Integration tests | ❌ not in CI |
| Frontend lint | ❌ not in CI |
| Alembic drift check | ❌ |
| Docker build | ❌ |
| Security scan | ❌ |

### 5.3 Recommended Release Pipeline 📋

```mermaid
flowchart LR
  A[Push tag] --> B[CI all tests]
  B --> C[Build images]
  C --> D[Push registry]
  D --> E[Deploy compose/k8s]
  E --> F[Smoke test /health]
```

---

## 6. Monitoring 📋

| Component | Tool | Status |
| --------- | ---- | ------ |
| Metrics | Prometheus + Grafana | 📋 |
| Logs | JSON → Loki/ELK | 📋 |
| Uptime | /health probe | ✅ endpoint exists |
| Celery | Flower | 📋 |

Key metrics to add: API latency, error rate, DB connections, import duration.

---

## 7. Backup & Recovery

| Object | Method | RPO Target |
| ------ | ------ | ---------- |
| PostgreSQL | pg_dump daily | 24h |
| SQLite dev | file copy | — |
| Config | git + secret manager | — |

Recovery:

```bash
docker compose down
psql rackdcim < backup.sql
docker compose up -d
curl http://localhost/health
```

---

## 8. Upgrade Procedure

1. Backup database
2. `alembic upgrade head`
3. Build new images
4. `docker compose up -d`
5. Verify `/health` and login
6. Rollback: restore backup + previous image tag

---

## References

- [07-Backend-Design.md](07-Backend-Design.md)
- [11-Security.md](11-Security.md)
- [14-Roadmap.md](14-Roadmap.md)
