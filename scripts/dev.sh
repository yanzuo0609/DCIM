#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"

port_listening() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "sport = :$port" 2>/dev/null | grep -q ":$port"
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  else
    return 1
  fi
}

wait_http_ok() {
  local url="$1"
  local timeout_sec="${2:-45}"
  local i=0
  while [ "$i" -lt "$timeout_sec" ]; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done
  return 1
}

ensure_backend_deps() {
  local venv_python stamp req_file hash
  if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
    venv_python="$BACKEND_DIR/.venv/bin/python"
  elif [ -x "$BACKEND_DIR/.venv/Scripts/python.exe" ]; then
    venv_python="$BACKEND_DIR/.venv/Scripts/python.exe"
  else
    echo "Creating backend virtualenv..."
    python -m venv "$BACKEND_DIR/.venv"
    if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
      venv_python="$BACKEND_DIR/.venv/bin/python"
    else
      venv_python="$BACKEND_DIR/.venv/Scripts/python.exe"
    fi
  fi

  req_file="$BACKEND_DIR/requirements.txt"
  stamp="$BACKEND_DIR/.venv/.deps.stamp"
  hash="$(sha256sum "$req_file" | awk '{print $1}')"
  if [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$hash" ] && \
     "$venv_python" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    echo "Backend dependencies up to date."
  else
    echo "Installing backend dependencies..."
    "$venv_python" -m pip install --upgrade pip -q -i "$PIP_INDEX"
    "$venv_python" -m pip install -r "$req_file" -q -i "$PIP_INDEX"
    "$venv_python" -m pip install pytest pytest-asyncio httpx -q -i "$PIP_INDEX"
    printf '%s' "$hash" > "$stamp"
  fi
}

ensure_frontend_deps() {
  local lock_file stamp hash
  lock_file="$FRONTEND_DIR/package-lock.json"
  stamp="$FRONTEND_DIR/node_modules/.deps.stamp"
  if [ -d "$FRONTEND_DIR/node_modules" ] && [ -f "$stamp" ] && [ -f "$lock_file" ]; then
    hash="$(sha256sum "$lock_file" | awk '{print $1}')"
    if [ "$(cat "$stamp")" = "$hash" ]; then
      echo "Frontend dependencies up to date."
      return 0
    fi
  fi
  echo "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install --silent)
  if [ -f "$lock_file" ]; then
    sha256sum "$lock_file" | awk '{print $1}' > "$stamp"
  fi
}

echo "Starting RackDCIM Pro development environment..."

ensure_backend_deps
ensure_frontend_deps

if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
  VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"
else
  VENV_PYTHON="$BACKEND_DIR/.venv/Scripts/python.exe"
fi

BACKEND_PID=""
FRONTEND_PID=""

if port_listening 8000; then
  echo "Backend already listening on :8000"
else
  echo "Starting backend on :8000 ..."
  (
    cd "$BACKEND_DIR"
    "$VENV_PYTHON" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ) &
  BACKEND_PID=$!
fi

if port_listening 5173; then
  echo "Frontend already listening on :5173"
else
  echo "Starting frontend on :5173 ..."
  (
    cd "$FRONTEND_DIR"
    npm run dev -- --host 0.0.0.0 --port 5173
  ) &
  FRONTEND_PID=$!
fi

if wait_http_ok "http://127.0.0.1:8000/api/v1/health"; then
  echo "Backend:  http://localhost:8000"
  echo "API Docs: http://localhost:8000/api/v1/docs"
else
  echo "Backend:  failed to become healthy within timeout" >&2
fi

if wait_http_ok "http://127.0.0.1:5173/"; then
  echo "Frontend: http://localhost:5173"
else
  echo "Frontend: failed to become ready within timeout" >&2
fi

cleanup() {
  if [ -n "${BACKEND_PID}" ]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [ -n "${FRONTEND_PID}" ]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

# Keep script alive when we started child processes in this shell.
if [ -n "${BACKEND_PID}${FRONTEND_PID}" ]; then
  wait
fi
