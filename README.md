# RackDCIM Pro

> AI Native Data Center Infrastructure Management Platform

RackDCIM Pro 是一款企业级、私有化部署的数据中心基础设施管理（DCIM）平台，采用 Documentation Driven Development（文档驱动开发）模式。

## Features (V1.0 Roadmap)

- 数据中心 / 机房 / 机柜 / 设备管理
- 自动上架与 SVG 机柜图
- Dashboard 可视化
- Excel / PDF 导入导出
- RBAC 权限管理

## Tech Stack

| Layer     | Technology                          |
| --------- | ----------------------------------- |
| Backend   | Python 3.12, FastAPI, SQLAlchemy    |
| Frontend  | Vue 3, TypeScript, Element Plus     |
| Database  | SQLite (dev) / PostgreSQL 16 (prod) |
| Queue     | Celery + Redis                      |
| Deploy    | Docker, Docker Compose, Nginx       |

## Project Structure

```text
rackdcim-pro/
├── backend/          # FastAPI backend (唯一后端入口)
│   ├── app/          # api / core / domains / models / repos / schemas / services
│   ├── alembic/      # DB migrations
│   └── requirements.txt
├── frontend/         # Vue 3 frontend (唯一前端入口)
├── deployment/       # Docker & Nginx configs
├── docs/             # Single Source of Truth
├── tests/            # Unit & integration tests
├── scripts/          # Dev & utility scripts
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- (Optional) Docker & Docker Compose

### One-command development

**Windows:**

```powershell
.\scripts\dev.ps1
```

**Linux / macOS:**

```bash
./scripts/dev.sh
```

脚本会按需创建虚拟环境、仅在依赖变更时安装包，并探测端口与健康状态。

### Manual development

**Backend:**

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

**Seed defaults (from repo root):**

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\seed.py
```

### URLs

| Service   | URL                               |
| --------- | --------------------------------- |
| Frontend  | http://localhost:5173             |
| Backend   | http://localhost:8000             |
| API Docs  | http://localhost:8000/api/v1/docs |
| Health    | http://localhost:8000/api/v1/health |

### Docker (Production-like)

```bash
cd deployment
docker compose up -d --build
```

## Documentation

All development follows docs as Single Source of Truth:

| Doc | Description          |
| --- | -------------------- |
| [00-Project.md](docs/00-Project.md) | Project overview     |
| [01-PRD.md](docs/01-PRD.md)         | Product requirements |
| [14-Roadmap.md](docs/14-Roadmap.md) | Milestones & roadmap |

## Development Workflow

```text
Project → PRD → Architecture → Database → API → Backend → Frontend → Algorithm → Testing → Release
```

## Branch Strategy

Git Flow: `main` / `release` / `develop` / `feature/*` / `bugfix/*` / `hotfix/*`

## License

Apache License 2.0 — see [LICENSE](LICENSE)
