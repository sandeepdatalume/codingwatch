"""Claude Code Mission Control — Metrics Collector."""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from collector import config
from collector.db import close_db, get_all_sessions, get_dashboard_stats, ingest, init_db, init_pg
from collector.models import MetricPayload
from collector.otlp import build_otlp_payload, push_otlp
from collector.prometheus import render_prometheus_metrics

# Resolve dashboard path (works from installed or repo location)
_DASHBOARD_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "dashboard" / "index.html",
    Path.home() / ".codingwatch" / "dashboard" / "index.html",
]

# Logging setup
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE, mode="a"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    await init_db()
    init_pg()
    logger.info(f"Collector started on port {config.COLLECTOR_PORT}")
    logger.info(f"SQLite: {config.SQLITE_PATH}")
    if config.DATABASE_URL:
        logger.info("PostgreSQL dual-write enabled")
    if config.OTLP_ENDPOINT:
        logger.info(f"OTLP push: {config.OTLP_ENDPOINT}")
    yield
    await close_db()


app = FastAPI(title="Claude Code Mission Control", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/metrics")
async def ingest_metrics(request: Request):
    """Ingest a metric payload from the statusline script."""
    try:
        raw = await request.body()
        raw_str = raw.decode("utf-8")
    except Exception:
        return Response(content='{"error":"invalid body"}', status_code=400, media_type="application/json")

    try:
        data = json.loads(raw_str)
    except json.JSONDecodeError:
        return Response(content='{"error":"invalid JSON"}', status_code=400, media_type="application/json")

    try:
        payload = MetricPayload(**data)
    except Exception as e:
        logger.warning(f"Payload validation warning (ingesting anyway): {e}")
        payload = MetricPayload()

    session_id = await ingest(payload, raw_str)

    # Fire-and-forget OTLP push if configured
    if config.OTLP_ENDPOINT:
        try:
            sessions = await get_all_sessions()
            await push_otlp(sessions)
        except Exception as e:
            logger.warning(f"OTLP push error: {e}")

    return {"status": "ok", "session_id": session_id}


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    sessions = await get_all_sessions()
    text = render_prometheus_metrics(sessions)
    return Response(content=text, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/api/v1/stats")
async def dashboard_stats():
    """Dashboard data endpoint — aggregated session stats."""
    stats = await get_dashboard_stats()
    return stats


@app.get("/api/v1/export/otlp")
async def otlp_export():
    """OTLP/HTTP JSON pull endpoint."""
    sessions = await get_all_sessions()
    payload = build_otlp_payload(sessions)
    return payload


@app.get("/", response_class=Response)
async def dashboard():
    """Serve the live dashboard."""
    for path in _DASHBOARD_CANDIDATES:
        if path.is_file():
            return Response(content=path.read_text(), media_type="text/html")
    return Response(content="Dashboard not found", status_code=404, media_type="text/plain")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "collector.app:app",
        host="0.0.0.0",
        port=config.COLLECTOR_PORT,
        log_level=config.LOG_LEVEL.lower(),
    )
