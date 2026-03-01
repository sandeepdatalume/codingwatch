"""Tests for database layer."""

import os
import tempfile

import pytest
import pytest_asyncio

from collector.db import close_db, get_all_sessions, get_dashboard_stats, ingest, init_db, insert_metric, upsert_session
from collector.models import (
    AgentInfo,
    ContextWindowInfo,
    CostInfo,
    CurrentUsage,
    MetricPayload,
    ModelInfo,
    OutputStyleInfo,
    VimInfo,
    WorkspaceInfo,
)


@pytest_asyncio.fixture
async def db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    conn = await init_db(db_path)
    yield conn
    await close_db()
    os.unlink(db_path)


@pytest.mark.asyncio
async def test_init_creates_tables(db):
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in await cursor.fetchall()]
    assert "sessions" in tables
    assert "metrics" in tables


@pytest.mark.asyncio
async def test_upsert_new_session(db):
    payload = MetricPayload(
        session_id="test-001",
        cwd="/home/dev/project",
        version="1.0.80",
        model=ModelInfo(id="claude-opus-4-6", display_name="Opus"),
        workspace=WorkspaceInfo(project_dir="/home/dev/project"),
    )
    sid = await upsert_session(payload, "{}")
    assert sid == "test-001"

    cursor = await db.execute("SELECT * FROM sessions WHERE session_id = ?", ("test-001",))
    row = await cursor.fetchone()
    assert row is not None
    d = dict(row)
    assert d["model_name"] == "Opus"
    assert d["cwd"] == "/home/dev/project"
    assert d["version"] == "1.0.80"


@pytest.mark.asyncio
async def test_upsert_existing_session_updates_last_seen(db):
    payload = MetricPayload(session_id="test-002", model=ModelInfo(display_name="Sonnet"))
    await upsert_session(payload, "{}")

    cursor = await db.execute("SELECT last_seen FROM sessions WHERE session_id = ?", ("test-002",))
    _first_seen = (await cursor.fetchone())[0]

    # Upsert again
    await upsert_session(payload, "{}")
    cursor = await db.execute("SELECT last_seen FROM sessions WHERE session_id = ?", ("test-002",))
    second_seen = (await cursor.fetchone())[0]

    assert second_seen is not None


@pytest.mark.asyncio
async def test_missing_session_id_generates_synthetic(db):
    payload = MetricPayload(model=ModelInfo(display_name="Haiku"))
    sid = await upsert_session(payload, "{}")
    assert sid.startswith("synthetic-")


@pytest.mark.asyncio
async def test_insert_metric_stores_all_fields(db):
    """Test with the full schema.json structure."""
    payload = MetricPayload(
        cwd="/home/dev/project",
        session_id="test-003",
        transcript_path="/path/to/transcript.jsonl",
        model=ModelInfo(id="claude-opus-4-6", display_name="Opus"),
        workspace=WorkspaceInfo(current_dir="/home/dev/project", project_dir="/home/dev/project"),
        version="1.0.80",
        output_style=OutputStyleInfo(name="default"),
        cost=CostInfo(
            total_cost_usd=0.05,
            total_duration_ms=60000,
            total_api_duration_ms=2300,
            total_lines_added=10,
            total_lines_removed=3,
        ),
        context_window=ContextWindowInfo(
            total_input_tokens=15234,
            total_output_tokens=4521,
            context_window_size=200000,
            used_percentage=45.2,
            remaining_percentage=54.8,
            current_usage=CurrentUsage(
                input_tokens=8500,
                output_tokens=1200,
                cache_creation_input_tokens=5000,
                cache_read_input_tokens=2000,
            ),
        ),
        exceeds_200k_tokens=False,
        vim=VimInfo(mode="NORMAL"),
        agent=AgentInfo(name="security-reviewer"),
    )
    await upsert_session(payload, '{"test": true}')
    await insert_metric("test-003", payload, '{"test": true}')

    cursor = await db.execute("SELECT * FROM metrics WHERE session_id = ?", ("test-003",))
    row = dict(await cursor.fetchone())
    assert row["cost_usd"] == 0.05
    assert row["duration_ms"] == 60000
    assert row["api_duration_ms"] == 2300
    assert row["lines_added"] == 10
    assert row["lines_removed"] == 3
    assert row["total_input_tokens"] == 15234
    assert row["total_output_tokens"] == 4521
    assert row["context_window_size"] == 200000
    assert row["used_percentage"] == 45.2
    assert row["remaining_percentage"] == 54.8
    assert row["current_input_tokens"] == 8500
    assert row["current_output_tokens"] == 1200
    assert row["cache_creation_input_tokens"] == 5000
    assert row["cache_read_input_tokens"] == 2000
    assert row["exceeds_200k_tokens"] == 0  # False stored as 0
    assert row["vim_mode"] == "NORMAL"
    assert row["agent_name"] == "security-reviewer"
    assert row["output_style"] == "default"
    assert row["transcript_path"] == "/path/to/transcript.jsonl"
    assert row["raw_json"] == '{"test": true}'


@pytest.mark.asyncio
async def test_insert_metric_with_none_fields(db):
    payload = MetricPayload(session_id="test-004")
    await upsert_session(payload, "{}")
    await insert_metric("test-004", payload, "{}")

    cursor = await db.execute("SELECT * FROM metrics WHERE session_id = ?", ("test-004",))
    row = dict(await cursor.fetchone())
    assert row["cost_usd"] == 0.0
    assert row["used_percentage"] is None
    assert row["vim_mode"] is None
    assert row["agent_name"] is None
    assert row["cache_creation_input_tokens"] == 0


@pytest.mark.asyncio
async def test_ingest_full_pipeline(db):
    payload = MetricPayload(
        session_id="test-005",
        model=ModelInfo(display_name="Opus"),
        cost=CostInfo(total_cost_usd=0.12),
        context_window=ContextWindowInfo(
            used_percentage=67.8,
            total_input_tokens=5000,
            total_output_tokens=2000,
        ),
    )
    sid = await ingest(payload, '{"full":"payload"}')
    assert sid == "test-005"

    sessions = await get_all_sessions()
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "test-005"
    assert sessions[0]["cost_usd"] == 0.12
    assert sessions[0]["total_input_tokens"] == 5000


@pytest.mark.asyncio
async def test_get_dashboard_stats(db):
    for i in range(3):
        payload = MetricPayload(
            session_id=f"dash-{i}",
            model=ModelInfo(display_name="Opus"),
            cost=CostInfo(total_cost_usd=0.10 * (i + 1)),
            context_window=ContextWindowInfo(
                used_percentage=30.0 + i * 20,
                total_input_tokens=1000 * (i + 1),
                total_output_tokens=500 * (i + 1),
                current_usage=CurrentUsage(
                    cache_creation_input_tokens=100 * (i + 1),
                    cache_read_input_tokens=50 * (i + 1),
                ),
            ),
        )
        await ingest(payload, "{}")

    stats = await get_dashboard_stats()
    assert len(stats["sessions"]) == 3
    assert stats["aggregate"]["total_cost"] == pytest.approx(0.60, abs=0.01)
    assert stats["aggregate"]["total_input_tokens"] == 6000
    assert stats["aggregate"]["total_output_tokens"] == 3000
    assert stats["aggregate"]["total_cache_creation_tokens"] == 600
    assert stats["aggregate"]["total_cache_read_tokens"] == 300
    assert len(stats["cost_history"]) == 3
    assert len(stats["context_history"]) == 3
