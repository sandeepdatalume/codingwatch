import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from collector import config
from collector.models import MetricPayload

logger = logging.getLogger(__name__)

# Module-level SQLite connection
_db: aiosqlite.Connection | None = None

# Optional PostgreSQL pool
_pg_pool = None

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    model_id TEXT,
    model_name TEXT,
    project_dir TEXT,
    workspace_dir TEXT,
    cwd TEXT,
    version TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cost_usd REAL,
    duration_ms INTEGER,
    api_duration_ms INTEGER,
    lines_added INTEGER,
    lines_removed INTEGER,
    total_input_tokens INTEGER,
    total_output_tokens INTEGER,
    context_window_size INTEGER,
    used_percentage REAL,
    remaining_percentage REAL,
    current_input_tokens INTEGER,
    current_output_tokens INTEGER,
    cache_creation_input_tokens INTEGER,
    cache_read_input_tokens INTEGER,
    exceeds_200k_tokens BOOLEAN,
    vim_mode TEXT,
    agent_name TEXT,
    output_style TEXT,
    transcript_path TEXT,
    raw_json TEXT
);
"""


async def init_db(db_path: str | None = None) -> aiosqlite.Connection:
    """Initialize SQLite database with WAL mode and create tables."""
    global _db
    path = db_path or config.SQLITE_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.executescript(SCHEMA_SQL)
    await _db.commit()
    logger.info(f"SQLite initialized at {path}")
    return _db


async def get_db() -> aiosqlite.Connection:
    """Get the active SQLite connection."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def close_db():
    """Close the SQLite connection."""
    global _db
    if _db:
        await _db.close()
        _db = None


def init_pg():
    """Initialize PostgreSQL connection pool if DATABASE_URL is set."""
    global _pg_pool
    if not config.DATABASE_URL:
        return
    try:
        from psycopg2 import pool

        _pg_pool = pool.ThreadedConnectionPool(1, 10, config.DATABASE_URL)
        conn = _pg_pool.getconn()
        cur = conn.cursor()
        cur.execute(SCHEMA_SQL.replace("AUTOINCREMENT", "GENERATED ALWAYS AS IDENTITY"))
        conn.commit()
        _pg_pool.putconn(conn)
        logger.info("PostgreSQL initialized")
    except Exception as e:
        logger.warning(f"PostgreSQL init failed (will use SQLite only): {e}")
        _pg_pool = None


def _ensure_session_id(payload: MetricPayload) -> str:
    """Return the session_id or generate a synthetic one."""
    if payload.session_id:
        return payload.session_id
    synthetic = f"synthetic-{uuid.uuid4().hex[:16]}"
    logger.info(f"Generated synthetic session_id: {synthetic}")
    return synthetic


async def upsert_session(payload: MetricPayload, raw_json: str) -> str:
    """Upsert a session record. Returns the session_id used."""
    db = await get_db()
    session_id = _ensure_session_id(payload)
    model_id = payload.model.id if payload.model else None
    model_name = payload.model.display_name if payload.model else None
    project_dir = payload.workspace.project_dir if payload.workspace else None
    workspace_dir = payload.workspace.current_dir if payload.workspace else None
    cwd = payload.cwd
    version = payload.version
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """INSERT INTO sessions
           (session_id, model_id, model_name, project_dir, workspace_dir, cwd, version, first_seen, last_seen)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(session_id) DO UPDATE SET
               last_seen = excluded.last_seen,
               model_id = COALESCE(excluded.model_id, sessions.model_id),
               model_name = COALESCE(excluded.model_name, sessions.model_name),
               project_dir = COALESCE(excluded.project_dir, sessions.project_dir),
               workspace_dir = COALESCE(excluded.workspace_dir, sessions.workspace_dir),
               cwd = COALESCE(excluded.cwd, sessions.cwd),
               version = COALESCE(excluded.version, sessions.version)
        """,
        (session_id, model_id, model_name, project_dir, workspace_dir, cwd, version, now, now),
    )
    await db.commit()
    return session_id


async def insert_metric(session_id: str, payload: MetricPayload, raw_json: str):
    """Insert a metric snapshot row."""
    db = await get_db()

    from collector.models import ContextWindowInfo, CostInfo

    cost = payload.cost if payload.cost is not None else CostInfo()
    ctx = payload.context_window if payload.context_window is not None else ContextWindowInfo()

    # Extract current_usage sub-fields
    cu = ctx.current_usage
    current_input_tokens = cu.input_tokens if cu else 0
    current_output_tokens = cu.output_tokens if cu else 0
    cache_creation = cu.cache_creation_input_tokens if cu else 0
    cache_read = cu.cache_read_input_tokens if cu else 0

    # vim, agent, output_style are now objects
    vim_mode = payload.vim.mode if payload.vim else None
    agent_name = payload.agent.name if payload.agent else None
    output_style = payload.output_style.name if payload.output_style else None

    await db.execute(
        """INSERT INTO metrics (
               session_id, cost_usd, duration_ms, api_duration_ms,
               lines_added, lines_removed, total_input_tokens, total_output_tokens,
               context_window_size, used_percentage, remaining_percentage,
               current_input_tokens, current_output_tokens,
               cache_creation_input_tokens, cache_read_input_tokens,
               exceeds_200k_tokens, vim_mode, agent_name, output_style,
               transcript_path, raw_json
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            cost.total_cost_usd,
            cost.total_duration_ms,
            cost.total_api_duration_ms,
            cost.total_lines_added,
            cost.total_lines_removed,
            ctx.total_input_tokens,
            ctx.total_output_tokens,
            ctx.context_window_size,
            ctx.used_percentage,
            ctx.remaining_percentage,
            current_input_tokens,
            current_output_tokens,
            cache_creation,
            cache_read,
            payload.exceeds_200k_tokens,
            vim_mode,
            agent_name,
            output_style,
            payload.transcript_path,
            raw_json,
        ),
    )
    await db.commit()


async def ingest(payload: MetricPayload, raw_json: str) -> str:
    """Full ingest pipeline: upsert session + insert metric. Returns session_id."""
    session_id = await upsert_session(payload, raw_json)
    await insert_metric(session_id, payload, raw_json)

    # Dual-write to PostgreSQL if available
    if _pg_pool:
        try:
            _pg_dual_write(session_id, payload, raw_json)
        except Exception as e:
            logger.warning(f"PostgreSQL dual-write failed (SQLite succeeded): {e}")

    return session_id


def _pg_dual_write(session_id: str, payload: MetricPayload, raw_json: str):
    """Write to PostgreSQL (synchronous, called from async context via thread)."""
    from collector.models import ContextWindowInfo, CostInfo

    conn = _pg_pool.getconn()
    try:
        cur = conn.cursor()
        model_id = payload.model.id if payload.model else None
        model_name = payload.model.display_name if payload.model else None
        project_dir = payload.workspace.project_dir if payload.workspace else None
        workspace_dir = payload.workspace.current_dir if payload.workspace else None
        now = datetime.now(timezone.utc).isoformat()

        cur.execute(
            """INSERT INTO sessions
               (session_id, model_id, model_name, project_dir, workspace_dir, cwd, version, first_seen, last_seen)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT(session_id) DO UPDATE SET
                   last_seen = EXCLUDED.last_seen,
                   model_id = COALESCE(EXCLUDED.model_id, sessions.model_id),
                   model_name = COALESCE(EXCLUDED.model_name, sessions.model_name)
            """,
            (session_id, model_id, model_name, project_dir, workspace_dir, payload.cwd, payload.version, now, now),
        )

        cost = payload.cost or CostInfo()
        ctx = payload.context_window or ContextWindowInfo()
        cu = ctx.current_usage
        vim_mode = payload.vim.mode if payload.vim else None
        agent_name = payload.agent.name if payload.agent else None
        output_style = payload.output_style.name if payload.output_style else None

        cur.execute(
            """INSERT INTO metrics (
                   session_id, cost_usd, duration_ms, api_duration_ms,
                   lines_added, lines_removed, total_input_tokens, total_output_tokens,
                   context_window_size, used_percentage, remaining_percentage,
                   current_input_tokens, current_output_tokens,
                   cache_creation_input_tokens, cache_read_input_tokens,
                   exceeds_200k_tokens, vim_mode, agent_name, output_style,
                   transcript_path, raw_json
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session_id,
                cost.total_cost_usd,
                cost.total_duration_ms,
                cost.total_api_duration_ms,
                cost.total_lines_added,
                cost.total_lines_removed,
                ctx.total_input_tokens,
                ctx.total_output_tokens,
                ctx.context_window_size,
                ctx.used_percentage,
                ctx.remaining_percentage,
                cu.input_tokens if cu else 0,
                cu.output_tokens if cu else 0,
                cu.cache_creation_input_tokens if cu else 0,
                cu.cache_read_input_tokens if cu else 0,
                payload.exceeds_200k_tokens,
                vim_mode,
                agent_name,
                output_style,
                payload.transcript_path,
                raw_json,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pg_pool.putconn(conn)


async def get_all_sessions():
    """Get all sessions with their latest metric."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT s.*, m.cost_usd, m.duration_ms, m.api_duration_ms,
                  m.lines_added, m.lines_removed, m.total_input_tokens, m.total_output_tokens,
                  m.context_window_size, m.used_percentage, m.remaining_percentage,
                  m.current_input_tokens, m.current_output_tokens,
                  m.cache_creation_input_tokens, m.cache_read_input_tokens,
                  m.exceeds_200k_tokens, m.vim_mode, m.agent_name, m.output_style,
                  m.transcript_path, m.ts as metric_ts
           FROM sessions s
           LEFT JOIN metrics m ON m.id = (
               SELECT id FROM metrics WHERE session_id = s.session_id ORDER BY ts DESC LIMIT 1
           )
           ORDER BY s.last_seen DESC
        """
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_dashboard_stats():
    """Get aggregated stats for the dashboard API."""
    db = await get_db()

    # All sessions with latest metrics
    sessions = await get_all_sessions()

    # Aggregate stats
    total_cost = sum(s.get("cost_usd") or 0 for s in sessions)
    total_input_tokens = sum(s.get("total_input_tokens") or 0 for s in sessions)
    total_output_tokens = sum(s.get("total_output_tokens") or 0 for s in sessions)
    total_cache_creation = sum(s.get("cache_creation_input_tokens") or 0 for s in sessions)
    total_cache_read = sum(s.get("cache_read_input_tokens") or 0 for s in sessions)

    # Active sessions (seen in last 10 minutes)
    cursor = await db.execute("SELECT COUNT(*) FROM sessions WHERE last_seen > datetime('now', '-10 minutes')")
    row = await cursor.fetchone()
    active_count = row[0] if row else 0

    # Cost history — last 500 metric snapshots
    cursor = await db.execute(
        """SELECT session_id, ts, cost_usd
           FROM metrics
           WHERE cost_usd IS NOT NULL
           ORDER BY ts DESC
           LIMIT 500
        """
    )
    cost_history = [dict(r) for r in await cursor.fetchall()]

    # Context history — last 500 snapshots
    cursor = await db.execute(
        """SELECT session_id, ts, used_percentage
           FROM metrics
           WHERE used_percentage IS NOT NULL
           ORDER BY ts DESC
           LIMIT 500
        """
    )
    context_history = [dict(r) for r in await cursor.fetchall()]

    return {
        "sessions": sessions,
        "aggregate": {
            "total_cost": total_cost,
            "active_count": active_count,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cache_creation_tokens": total_cache_creation,
            "total_cache_read_tokens": total_cache_read,
        },
        "cost_history": cost_history,
        "context_history": context_history,
    }
