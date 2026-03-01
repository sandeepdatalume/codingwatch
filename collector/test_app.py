"""Tests for FastAPI application endpoints."""

import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from collector import config

# Override SQLite path before importing app
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
config.SQLITE_PATH = _tmp.name
_tmp.close()

from collector.app import app  # noqa: E402
from collector.db import close_db, init_db  # noqa: E402


@pytest_asyncio.fixture
async def client():
    """Create an async test client with initialized DB."""
    await init_db(config.SQLITE_PATH)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await close_db()


# Full payload matching schema.json exactly
VALID_PAYLOAD = {
    "cwd": "/home/dev/myproject",
    "session_id": "test-app-001",
    "transcript_path": "/path/to/transcript.jsonl",
    "model": {"id": "claude-opus-4-6", "display_name": "Opus"},
    "workspace": {"current_dir": "/home/dev/myproject", "project_dir": "/home/dev/myproject"},
    "version": "1.0.80",
    "output_style": {"name": "default"},
    "cost": {
        "total_cost_usd": 0.0234,
        "total_duration_ms": 120000,
        "total_api_duration_ms": 2300,
        "total_lines_added": 45,
        "total_lines_removed": 12,
    },
    "context_window": {
        "total_input_tokens": 15234,
        "total_output_tokens": 4521,
        "context_window_size": 200000,
        "used_percentage": 34.5,
        "remaining_percentage": 65.5,
        "current_usage": {
            "input_tokens": 8500,
            "output_tokens": 1200,
            "cache_creation_input_tokens": 5000,
            "cache_read_input_tokens": 2000,
        },
    },
    "exceeds_200k_tokens": False,
    "vim": {"mode": "NORMAL"},
    "agent": {"name": "security-reviewer"},
}


@pytest.mark.asyncio
async def test_post_metrics_valid(client):
    resp = await client.post("/metrics", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["session_id"] == "test-app-001"


@pytest.mark.asyncio
async def test_post_metrics_invalid_json(client):
    resp = await client.post("/metrics", content="not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 400
    assert "invalid JSON" in resp.json()["error"]


@pytest.mark.asyncio
async def test_post_metrics_missing_fields(client):
    resp = await client.post("/metrics", json={"session_id": "minimal-001"})
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "minimal-001"


@pytest.mark.asyncio
async def test_post_metrics_empty_object(client):
    resp = await client.post("/metrics", json={})
    assert resp.status_code == 200
    assert resp.json()["session_id"].startswith("synthetic-")


@pytest.mark.asyncio
async def test_cors_headers(client):
    resp = await client.options(
        "/metrics",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" in resp.headers


@pytest.mark.asyncio
async def test_get_prometheus_metrics(client):
    await client.post("/metrics", json=VALID_PAYLOAD)
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "claude_session_cost_usd" in text
    assert "claude_session_cache_creation_tokens" in text
    assert "claude_session_cache_read_tokens" in text
    assert "claude_session_current_input_tokens" in text
    assert "claude_active_sessions_total" in text
    assert "claude_total_cost_usd" in text
    assert "# HELP" in text
    assert "# TYPE" in text


@pytest.mark.asyncio
async def test_get_dashboard_stats(client):
    await client.post("/metrics", json=VALID_PAYLOAD)
    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert "aggregate" in data
    assert "cost_history" in data
    assert "context_history" in data
    assert data["aggregate"]["total_cost"] >= 0
    assert "total_cache_creation_tokens" in data["aggregate"]
    assert "total_cache_read_tokens" in data["aggregate"]
    # Verify session has all schema fields
    session = data["sessions"][0]
    assert session["cache_creation_input_tokens"] == 5000
    assert session["cache_read_input_tokens"] == 2000
    assert session["vim_mode"] == "NORMAL"
    assert session["agent_name"] == "security-reviewer"
    assert session["output_style"] == "default"


@pytest.mark.asyncio
async def test_get_otlp_export(client):
    await client.post("/metrics", json=VALID_PAYLOAD)
    resp = await client.get("/api/v1/export/otlp")
    assert resp.status_code == 200
    data = resp.json()
    assert "resourceMetrics" in data
    rm = data["resourceMetrics"][0]
    # Check resource attributes
    attrs = {a["key"]: a["value"]["stringValue"] for a in rm["resource"]["attributes"]}
    assert attrs["service.name"] == "claude-code-metrics"
    assert attrs["service.version"] == "1.0.0"
    # Check scope
    assert rm["scopeMetrics"][0]["scope"]["name"] == "claude.statusline"
    # Check new cache metrics are present
    metric_names = {m["name"] for m in rm["scopeMetrics"][0]["metrics"]}
    assert "claude.session.cache_creation_tokens" in metric_names
    assert "claude.session.cache_read_tokens" in metric_names
    assert "claude.session.current_input_tokens" in metric_names
    assert "claude.session.current_output_tokens" in metric_names


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
