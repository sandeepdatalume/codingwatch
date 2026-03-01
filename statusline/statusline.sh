#!/usr/bin/env bash
set -euo pipefail

# Claude Code Mission Control — Statusline Script
# Reads JSON payload from stdin, prints status bar text to stdout,
# and POSTs the raw JSON to the collector in a background subprocess.

# Read entire stdin into variable
input="$(cat)"

# Collector URL — configurable via env var
CLAUDE_METRICS_URL="${CLAUDE_METRICS_URL:-http://localhost:9876/metrics}"

# Check if jq is available
if command -v jq &>/dev/null; then
    model=$(echo "$input" | jq -r '.model.display_name // "Unknown"' 2>/dev/null || echo "Unknown")
    cost=$(echo "$input" | jq -r '.cost.total_cost_usd // 0' 2>/dev/null || echo "0")
    used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // 0' 2>/dev/null || echo "0")
    lines_added=$(echo "$input" | jq -r '.cost.total_lines_added // 0' 2>/dev/null || echo "0")
    lines_removed=$(echo "$input" | jq -r '.cost.total_lines_removed // 0' 2>/dev/null || echo "0")
    vim_mode=$(echo "$input" | jq -r '.vim.mode // empty' 2>/dev/null || echo "")

    # Format cost as $X.XX
    cost_fmt=$(printf '$%.2f' "$cost" 2>/dev/null || echo "\$0.00")

    # Format context percentage
    ctx_fmt=$(printf '%.0f%%' "$used_pct" 2>/dev/null || echo "0%")

    # Build status line
    status="${model} | ${cost_fmt} | Ctx: ${ctx_fmt} | +${lines_added}/-${lines_removed}"

    # Append vim mode if present
    if [ -n "$vim_mode" ] && [ "$vim_mode" != "null" ]; then
        status="${status} | vim:${vim_mode}"
    fi
else
    # Fallback without jq — just show a basic status
    status="Mission Control active"
fi

# Print status bar text to stdout (this is what Claude Code displays)
echo "$status"

# POST the raw JSON to the collector in background — never block the status bar
if [ -n "$input" ]; then
    echo "$input" | curl -s -X POST "$CLAUDE_METRICS_URL" \
        -H "Content-Type: application/json" \
        --max-time 2 -d @- >/dev/null 2>&1 &
fi
