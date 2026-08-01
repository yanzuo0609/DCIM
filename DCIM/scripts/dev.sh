#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Starting RackDCIM Pro development environment..."

# Backend
cd "$ROOT_DIR/backend"
if [ ! -d ".venv" ]; then
  python -m venv .venv
fi
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
pip install -r requirements.txt -q
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Frontend
cd "$ROOT_DIR/frontend"
npm install -q
npm run dev &
FRONTEND_PID=$!

echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://localhost:8000/api/v1/docs"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
