---
name: db-migrate
description: Help with SQLite and PostgreSQL schema migrations for the metrics collector database.
user-invocable: true
disable-model-invocation: false
---

# Database Migration Skill

Guide schema changes for the Claude Code Mission Control collector database.

## Workflow

When the user wants to change the database schema:

1. **Read current schema** from `collector/db.py` — look at `CREATE TABLE` statements in `init_db()`
2. **Read models** from `collector/models.py` — understand the Pydantic models
3. **Plan migration** — determine what columns/tables to add, modify, or remove
4. **Generate SQL** — write the ALTER TABLE or new CREATE TABLE statements
5. **Update code** — modify `db.py` init, upsert, insert, and query functions
6. **Update models** — keep Pydantic models in sync
7. **Update renderers** — update `prometheus.py` and `otlp.py` if new metrics are exposed
8. **Run tests** — `python -m pytest collector/ -v`

## Key Files

| File | Purpose |
|------|---------|
| `collector/db.py` | Schema DDL, upsert/insert/query functions |
| `collector/models.py` | Pydantic models for JSON payload validation |
| `collector/prometheus.py` | Prometheus text format renderer |
| `collector/otlp.py` | OTLP/HTTP JSON payload builder |
| `collector/app.py` | FastAPI endpoints |
| `schema.json` | Source of truth for Claude Code payload structure |

## Migration Pattern

For SQLite, use this pattern to add columns safely:

```sql
-- Check if column exists before adding
ALTER TABLE sessions ADD COLUMN new_field TEXT DEFAULT NULL;
```

For PostgreSQL dual-write, update the `_pg_dual_write()` function in `db.py`.

## Important

- `schema.json` is the source of truth for the Claude Code payload structure — never modify it
- SQLite is the primary store; PostgreSQL is optional dual-write
- All new fields should have sensible defaults (NULL or 0) for backward compatibility
- Run all 33+ tests after any schema change
