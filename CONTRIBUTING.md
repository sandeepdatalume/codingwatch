# Contributing to codingwatch

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/datalume-io/codingwatch.git
cd codingwatch

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Verify everything works
python -m pytest collector/ -v
ruff check collector/
```

## Making Changes

1. **Create a branch** from `main`:
   ```bash
   git checkout -b your-feature-name
   ```

2. **Make your changes** — keep commits focused and atomic.

3. **Run lint and format**:
   ```bash
   ruff check collector/ --fix
   ruff format collector/
   ```

4. **Run tests**:
   ```bash
   python -m pytest collector/ -v
   ```

5. **Open a pull request** against `main`.

## Code Conventions

- **All payload fields are Optional with defaults** — Claude Code may omit any field at any time.
- **Duration values**: stored as milliseconds in the database, converted to seconds for Prometheus and OTLP export.
- **Prometheus labels**: `session_id` (first 16 chars), `model`, `project`.
- **OTLP attributes**: full `session_id`, `model`, `project`.
- **Dashboard security**: no `innerHTML` — use safe DOM methods only (`createElement`, `textContent`).
- **`schema.json` is read-only** — it documents Claude Code's payload structure. Never modify it.
- **SQLite WAL mode** for concurrent write safety.
- **Tests use temporary databases** — never touch production data.

## Architecture Notes

The data pipeline flows in one direction:

```
statusline.sh → POST /metrics → SQLite (+ optional PostgreSQL)
                                    ↓
                          GET /metrics (Prometheus)
                          GET /api/v1/export/otlp
                          GET /api/v1/stats (dashboard)
```

Key files:
- `collector/models.py` — Pydantic models (must match `schema.json`)
- `collector/db.py` — Storage layer (SQLite primary, PostgreSQL optional)
- `collector/prometheus.py` — Prometheus text format renderer
- `collector/otlp.py` — OTLP/HTTP JSON builder

## Reporting Issues

When reporting a bug, please include:

- Python version (`python3 --version`)
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant log output (check `~/.claude/metrics-collector.log`)

For feature requests, describe the use case and how it fits with the project's goal of observability for AI coding agents.
