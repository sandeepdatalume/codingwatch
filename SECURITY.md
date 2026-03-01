# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do not open a public issue.** Instead, email security@datalume.io with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact

We will acknowledge your report within 48 hours and provide a timeline for a fix.

## Scope

This project collects metrics about AI coding sessions. The following are in scope:

- Unauthorized access to the collector API
- SQL injection in the database layer
- XSS in the dashboard
- Information disclosure via metrics endpoints

## Default Credentials

The `docker-compose.yml` includes default development credentials (`claude`/`claude` for PostgreSQL, `admin` for Grafana). These are intended for local development only and must be changed for any internet-facing deployment.
