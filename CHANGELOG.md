# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-01

### Added

- FastAPI metrics collector with SQLite primary storage
- PostgreSQL optional dual-write support
- Prometheus-compatible `/metrics` endpoint with per-session gauges
- OTLP/HTTP JSON export (pull via `/api/v1/export/otlp`, push to configurable endpoint)
- Single-file HTML dashboard with real-time session overview
- Bash statusline script for Claude Code integration
- Docker Compose stack (collector, Postgres, Prometheus, Grafana)
- One-command local setup via `setup.sh`
- 33+ tests across database, API, Prometheus, and OTLP layers
- GitHub Actions CI with Python 3.10/3.11/3.12 matrix

[0.1.0]: https://github.com/datalume-io/codingwatch/releases/tag/v0.1.0
