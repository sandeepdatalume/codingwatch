#!/usr/bin/env bash
set -euo pipefail

# codingwatch — One-command local setup
# Installs dependencies, copies statusline script, starts collector

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
PID_FILE="$CLAUDE_DIR/metrics-collector.pid"
LOG_FILE="$CLAUDE_DIR/metrics-collector.log"

echo "=== codingwatch Setup ==="
echo ""

# 1. Check Python 3.10+
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.10+ first."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "ERROR: Python 3.10+ required (found $PY_VERSION)"
    exit 1
fi
echo "[OK] Python $PY_VERSION"

# 2. Check for jq
if ! command -v jq &>/dev/null; then
    echo "WARNING: jq not found. The statusline will work but with reduced functionality."
    echo "  Install: brew install jq (macOS) or apt install jq (Linux)"
fi

# 3. Create .claude directory
mkdir -p "$CLAUDE_DIR"

# 4. Set up Python venv and install dependencies
echo ""
echo "Installing Python dependencies..."
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    python3 -m venv "$SCRIPT_DIR/venv"
fi
source "$SCRIPT_DIR/venv/bin/activate"
pip install -q -r "$SCRIPT_DIR/collector/requirements.txt"
echo "[OK] Dependencies installed"

# 5. Copy statusline script
cp "$SCRIPT_DIR/statusline/statusline.sh" "$CLAUDE_DIR/statusline.sh"
chmod +x "$CLAUDE_DIR/statusline.sh"
echo "[OK] Statusline script installed to $CLAUDE_DIR/statusline.sh"

# 6. Stop existing collector if running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Stopping existing collector (PID $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

# 7. Start collector
echo ""
echo "Starting collector..."
cd "$SCRIPT_DIR"
nohup "$SCRIPT_DIR/venv/bin/python" -m collector.app > "$LOG_FILE" 2>&1 &
COLLECTOR_PID=$!
echo "$COLLECTOR_PID" > "$PID_FILE"
sleep 1

# Verify it started
if kill -0 "$COLLECTOR_PID" 2>/dev/null; then
    echo "[OK] Collector running (PID $COLLECTOR_PID) on http://localhost:9876"
else
    echo "ERROR: Collector failed to start. Check $LOG_FILE"
    exit 1
fi

# 8. Print summary
echo ""
echo "=== Setup Complete ==="
echo ""
echo "  Collector:  http://localhost:9876"
echo "  Dashboard:  file://$SCRIPT_DIR/dashboard/index.html"
echo "  SQLite DB:  $CLAUDE_DIR/metrics.db"
echo "  Logs:       $LOG_FILE"
echo ""
echo "Configure Claude Code statusline:"
echo "  Add to ~/.claude/settings.json:"
echo "    \"statusLine\": { \"type\": \"command\", \"command\": \"$CLAUDE_DIR/statusline.sh\" }"
echo ""
echo "Verify with:"
echo "  curl -s http://localhost:9876/health"
echo ""
echo "To stop the collector:"
echo "  kill \$(cat $PID_FILE)"
