#!/usr/bin/env bash
set -euo pipefail

# codingwatch — one-command installer
# Usage: curl -fsSL https://raw.githubusercontent.com/sandeepdatalume/codingwatch/main/install.sh | bash

INSTALL_DIR="$HOME/.codingwatch"
CLAUDE_DIR="$HOME/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
PID_FILE="$CLAUDE_DIR/metrics-collector.pid"
LOG_FILE="$CLAUDE_DIR/metrics-collector.log"
REPO="https://github.com/sandeepdatalume/codingwatch.git"

echo "=== codingwatch installer ==="
echo ""

# 1. Check dependencies
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

if ! command -v git &>/dev/null; then
    echo "ERROR: git not found."
    exit 1
fi

# 2. Clone or update repo
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating existing installation..."
    git -C "$INSTALL_DIR" pull --quiet
else
    echo "Cloning codingwatch..."
    rm -rf "$INSTALL_DIR"
    git clone --quiet "$REPO" "$INSTALL_DIR"
fi
echo "[OK] Source at $INSTALL_DIR"

# 3. Set up venv and install deps
echo "Installing dependencies..."
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi
"$INSTALL_DIR/venv/bin/pip" install -q -r "$INSTALL_DIR/collector/requirements.txt"
echo "[OK] Dependencies installed"

# 4. Install statusline script
mkdir -p "$CLAUDE_DIR"
cp "$INSTALL_DIR/statusline/statusline.sh" "$CLAUDE_DIR/statusline.sh"
chmod +x "$CLAUDE_DIR/statusline.sh"
echo "[OK] Statusline installed"

# 5. Configure Claude Code settings
if [ -f "$SETTINGS_FILE" ]; then
    # Check if statusLine is already configured
    if python3 -c "import json; d=json.load(open('$SETTINGS_FILE')); exit(0 if 'statusLine' in d else 1)" 2>/dev/null; then
        echo "[OK] Claude Code statusLine already configured"
    else
        # Merge statusLine into existing settings
        python3 -c "
import json
with open('$SETTINGS_FILE') as f:
    d = json.load(f)
d['statusLine'] = {'type': 'command', 'command': '$CLAUDE_DIR/statusline.sh'}
with open('$SETTINGS_FILE', 'w') as f:
    json.dump(d, f, indent=2)
"
        echo "[OK] Claude Code statusLine configured"
    fi
else
    # Create new settings file
    python3 -c "
import json
d = {'statusLine': {'type': 'command', 'command': '$CLAUDE_DIR/statusline.sh'}}
with open('$SETTINGS_FILE', 'w') as f:
    json.dump(d, f, indent=2)
"
    echo "[OK] Claude Code settings created"
fi

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
cd "$INSTALL_DIR"
nohup "$INSTALL_DIR/venv/bin/python" -m collector.app > "$LOG_FILE" 2>&1 &
COLLECTOR_PID=$!
echo "$COLLECTOR_PID" > "$PID_FILE"
sleep 1

if kill -0 "$COLLECTOR_PID" 2>/dev/null; then
    echo "[OK] Collector running on http://localhost:9876"
else
    echo "ERROR: Collector failed to start. Check $LOG_FILE"
    exit 1
fi

# 8. Open dashboard in browser
DASHBOARD_URL="http://localhost:9876"
if command -v open &>/dev/null; then
    open "$DASHBOARD_URL"
elif command -v xdg-open &>/dev/null; then
    xdg-open "$DASHBOARD_URL"
fi

# 9. Done
echo ""
echo "=== codingwatch installed ==="
echo ""
echo "  Dashboard:  $DASHBOARD_URL"
echo "  Health:     curl $DASHBOARD_URL/health"
echo ""
echo "Restart any running Claude Code sessions to start collecting metrics."
echo ""
