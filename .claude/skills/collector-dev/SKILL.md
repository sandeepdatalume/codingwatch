---
name: collector-dev
description: Manage the Claude Code metrics collector lifecycle — start, stop, restart, check status, and tail logs.
user-invocable: true
disable-model-invocation: false
---

# Collector Development Skill

Manage the FastAPI metrics collector for Claude Code Mission Control.

## Commands

When the user invokes `/collector-dev`, determine the intent from their message. Default to `status` if unclear.

### start
```bash
cd "$PROJECT_DIR"
source .venv/bin/activate 2>/dev/null || true
python -m collector.app &
echo $! > /tmp/claude-collector.pid
echo "Collector started (PID $(cat /tmp/claude-collector.pid)) on port ${COLLECTOR_PORT:-9876}"
```

### stop
```bash
if [ -f /tmp/claude-collector.pid ]; then
  kill "$(cat /tmp/claude-collector.pid)" 2>/dev/null && echo "Collector stopped" || echo "Process not running"
  rm -f /tmp/claude-collector.pid
else
  echo "No PID file found. Checking for running process..."
  pkill -f "python -m collector.app" && echo "Collector stopped" || echo "No collector running"
fi
```

### restart
Stop then start.

### status
```bash
# Check if running
if [ -f /tmp/claude-collector.pid ] && kill -0 "$(cat /tmp/claude-collector.pid)" 2>/dev/null; then
  echo "Collector running (PID $(cat /tmp/claude-collector.pid))"
else
  echo "Collector not running"
fi

# Check health endpoint
curl -s http://localhost:${COLLECTOR_PORT:-9876}/health 2>/dev/null || echo "Health endpoint unreachable"

# Show active sessions count
curl -s http://localhost:${COLLECTOR_PORT:-9876}/api/v1/stats 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Active sessions: {len(d[\"sessions\"])}')" 2>/dev/null || true
```

### logs
```bash
tail -50 "${LOG_FILE:-/tmp/claude-collector.log}"
```

### test
```bash
cd "$PROJECT_DIR"
source .venv/bin/activate 2>/dev/null || true
python -m pytest collector/ -v
```

## Environment Variables

- `COLLECTOR_PORT` — port (default 9876)
- `SQLITE_PATH` — database location (default ~/.claude/metrics.db)
- `DATABASE_URL` — optional PostgreSQL connection string
- `OTLP_ENDPOINT` — optional OTLP push target
- `LOG_LEVEL` — DEBUG, INFO, WARNING, ERROR (default INFO)
