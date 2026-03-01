# Claude Code Mission Control

Real-time observability platform for Claude Code sessions. Captures metrics via statusline hook, stores in SQLite, and exposes through Prometheus, OTLP, and a live dashboard.

## Architecture

```
statusline.sh (stdin JSON → stdout status text → background POST)
    ↓
FastAPI collector (port 9876)
    ↓
SQLite (primary) + PostgreSQL (optional dual-write)
    ↓
GET /metrics (Prometheus) | GET /api/v1/export/otlp | GET /api/v1/stats (dashboard)
```

## Key Files

| File | Purpose |
|------|---------|
| `schema.json` | **Source of truth** — Claude Code's JSON payload structure. NEVER modify. |
| `collector/models.py` | Pydantic models matching schema.json |
| `collector/db.py` | SQLite/PostgreSQL schema, upsert, insert, query |
| `collector/app.py` | FastAPI endpoints |
| `collector/prometheus.py` | Prometheus text format renderer |
| `collector/otlp.py` | OTLP/HTTP JSON builder |
| `collector/config.py` | Environment variable configuration |
| `statusline/statusline.sh` | Bash statusline hook script |
| `dashboard/index.html` | Single-file dashboard (no build step) |

## Development

```bash
# Activate venv
source .venv/bin/activate

# Run tests
python -m pytest collector/ -v

# Start collector locally
python -m collector.app

# Run with Docker
docker compose up -d
```

## Conventions

- All payload fields are **Optional with defaults** — Claude Code may omit any field
- Duration values: stored as milliseconds in DB, converted to seconds for Prometheus/OTLP
- Prometheus labels: `session_id` (first 16 chars), `model`, `project`
- OTLP attributes: full `session_id`, `model`, `project`
- Dashboard: no innerHTML — use safe DOM methods only (createElement/textContent)
- SQLite WAL mode for concurrent write safety
- All tests use temporary SQLite databases (never touch production DB)

## Testing

33+ tests across 4 test files:
- `collector/test_db.py` — database layer
- `collector/test_app.py` — FastAPI endpoints (async)
- `collector/test_prometheus.py` — Prometheus output
- `collector/test_otlp.py` — OTLP payload structure

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `COLLECTOR_PORT` | 9876 | Collector HTTP port |
| `SQLITE_PATH` | ~/.claude/metrics.db | SQLite database location |
| `DATABASE_URL` | (none) | PostgreSQL connection string |
| `OTLP_ENDPOINT` | (none) | OTLP push target URL |
| `LOG_LEVEL` | INFO | Logging level |
