#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"
LOG_DIR="$ROOT_DIR/runtime_logs"
WORKSPACE_ROOT="${NEW_APP_WORKSPACE_ROOT:-$ROOT_DIR/.runtime-data/users}"
PID_FILE="$RUNTIME_DIR/govdoc_agent.pid"
LOG_FILE="$LOG_DIR/govdoc_agent.log"
HOST="${NEW_APP_HOST:-127.0.0.1}"
PORT="${NEW_APP_PORT:-8000}"

LEGACY_AUTH_BASE_URL="${LEGACY_AUTH_BASE_URL:-http://127.0.0.1:8080/areport}"
LEGACY_SERVICE_BASE_URL="${LEGACY_SERVICE_BASE_URL:-http://127.0.0.1:8080/areport}"
LEGACY_SYSTEM_URL="${LEGACY_SYSTEM_URL:-http://127.0.0.1:8081/document/}"
ENABLE_DEV_AUTH_MOCK="${ENABLE_DEV_AUTH_MOCK:-true}"
NEW_APP_DEBUG_RUNTIME_LOGS="${NEW_APP_DEBUG_RUNTIME_LOGS:-true}"
NEW_APP_DEBUG_LOG_MAX_CHARS="${NEW_APP_DEBUG_LOG_MAX_CHARS:-40000}"
NEW_APP_DEBUG_LOG_MAX_STRING_CHARS="${NEW_APP_DEBUG_LOG_MAX_STRING_CHARS:-12000}"

mkdir -p "$RUNTIME_DIR" "$LOG_DIR" "$WORKSPACE_ROOT"

resolve_python() {
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    echo "$ROOT_DIR/.venv/bin/python"
  else
    command -v python3
  fi
}

resolve_pid() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "$pid"
      return 0
    fi
  fi

  local pid
  pid="$(pgrep -f "uvicorn app.main:app --host ${HOST} --port ${PORT}" | head -n 1 || true)"
  if [[ -n "${pid}" ]]; then
    echo "$pid" > "$PID_FILE"
    echo "$pid"
    return 0
  fi

  return 1
}

wait_for_health() {
  local url="http://${HOST}:${PORT}/api/agentloop/health"
  for _ in {1..20}; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

start_backend() {
  if pid="$(resolve_pid)"; then
    echo "govdoc-agent is already running. pid=${pid}"
    echo "log: $LOG_FILE"
    return 0
  fi

  local py_bin
  py_bin="$(resolve_python)"

  echo "Starting govdoc-agent..."
  echo "log: $LOG_FILE"

  export ROOT_DIR
  export PID_FILE
  export LOG_FILE
  export HOST
  export PORT
  export LEGACY_AUTH_BASE_URL
  export LEGACY_SERVICE_BASE_URL
  export LEGACY_SYSTEM_URL
  export ENABLE_DEV_AUTH_MOCK
  export NEW_APP_DEBUG_RUNTIME_LOGS
  export NEW_APP_DEBUG_LOG_MAX_CHARS
  export NEW_APP_DEBUG_LOG_MAX_STRING_CHARS
  export NEW_APP_WORKSPACE_ROOT="$WORKSPACE_ROOT"
  export PY_BIN="$py_bin"

  "$py_bin" - <<'PY'
import os
import subprocess
from pathlib import Path

root_dir = Path(os.environ["ROOT_DIR"])
log_file = Path(os.environ["LOG_FILE"])
pid_file = Path(os.environ["PID_FILE"])
py_bin = os.environ["PY_BIN"]
host = os.environ["HOST"]
port = os.environ["PORT"]

env = os.environ.copy()
with log_file.open("a", encoding="utf-8") as log_handle:
    proc = subprocess.Popen(
        [py_bin, "-m", "uvicorn", "app.main:app", "--host", host, "--port", port],
        cwd=root_dir,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
pid_file.write_text(str(proc.pid), encoding="utf-8")
PY

  local pid
  pid="$(cat "$PID_FILE")"
  if wait_for_health; then
    echo "govdoc-agent started successfully. pid=${pid}"
    echo "health: http://${HOST}:${PORT}/api/agentloop/health"
  else
    echo "govdoc-agent start command sent, but health check did not pass yet."
    echo "pid=${pid}"
    echo "check log: $LOG_FILE"
    return 1
  fi
}

run_backend_foreground() {
  local py_bin
  py_bin="$(resolve_python)"

  echo "Running govdoc-agent in foreground..."
  echo "terminal logs: enabled"
  echo "health: http://${HOST}:${PORT}/api/agentloop/health"

  cd "$ROOT_DIR"
  export LEGACY_AUTH_BASE_URL
  export LEGACY_SERVICE_BASE_URL
  export LEGACY_SYSTEM_URL
  export ENABLE_DEV_AUTH_MOCK
  export NEW_APP_DEBUG_RUNTIME_LOGS
  export NEW_APP_DEBUG_LOG_MAX_CHARS
  export NEW_APP_DEBUG_LOG_MAX_STRING_CHARS
  export NEW_APP_WORKSPACE_ROOT="$WORKSPACE_ROOT"
  exec "$py_bin" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
}

stop_backend() {
  local pid
  if ! pid="$(resolve_pid)"; then
    rm -f "$PID_FILE"
    echo "govdoc-agent is not running."
    return 0
  fi

  echo "Stopping govdoc-agent... pid=${pid}"
  kill "$pid" 2>/dev/null || true

  for _ in {1..10}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$PID_FILE"
      echo "govdoc-agent stopped."
      return 0
    fi
    sleep 1
  done

  echo "Process did not exit in time, forcing stop..."
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$PID_FILE"
  echo "govdoc-agent stopped."
}

status_backend() {
  if pid="$(resolve_pid)"; then
    echo "govdoc-agent is running. pid=${pid}"
    if curl -fsS "http://${HOST}:${PORT}/api/agentloop/health" >/dev/null 2>&1; then
      echo "health: ok"
    else
      echo "health: unavailable"
    fi
    echo "log: $LOG_FILE"
  else
    echo "govdoc-agent is not running."
  fi
}

show_logs() {
  touch "$LOG_FILE"
  tail -f "$LOG_FILE"
}

usage() {
  cat <<EOF
Usage: $(basename "$0") {start|dev|stop|restart|status|logs}

Defaults:
  HOST=$HOST
  PORT=$PORT
  ENABLE_DEV_AUTH_MOCK=$ENABLE_DEV_AUTH_MOCK
  NEW_APP_DEBUG_RUNTIME_LOGS=$NEW_APP_DEBUG_RUNTIME_LOGS
  NEW_APP_DEBUG_LOG_MAX_CHARS=$NEW_APP_DEBUG_LOG_MAX_CHARS
  NEW_APP_DEBUG_LOG_MAX_STRING_CHARS=$NEW_APP_DEBUG_LOG_MAX_STRING_CHARS
  LLM_CONFIG=$ROOT_DIR/config/model.json
  LEGACY_AUTH_BASE_URL=$LEGACY_AUTH_BASE_URL
  LEGACY_SERVICE_BASE_URL=$LEGACY_SERVICE_BASE_URL
  LEGACY_SYSTEM_URL=$LEGACY_SYSTEM_URL
  NEW_APP_WORKSPACE_ROOT=$WORKSPACE_ROOT

Examples:
  ./manage_govdoc_agent.sh start
  ./manage_govdoc_agent.sh dev
  ./manage_govdoc_agent.sh stop
  ENABLE_DEV_AUTH_MOCK=false ./manage_govdoc_agent.sh restart
EOF
}

case "${1:-}" in
  start)
    start_backend
    ;;
  dev)
    run_backend_foreground
    ;;
  stop)
    stop_backend
    ;;
  restart)
    stop_backend
    start_backend
    ;;
  status)
    status_backend
    ;;
  logs)
    show_logs
    ;;
  *)
    usage
    exit 1
    ;;
esac
