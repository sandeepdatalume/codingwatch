"""OTLP/HTTP JSON payload builder and async push."""

import logging
import time
from typing import Any

import httpx

from collector import config

logger = logging.getLogger(__name__)


def _gauge_metric(name: str, description: str, unit: str, datapoints: list[dict]) -> dict:
    """Build a single OTLP gauge metric."""
    return {
        "name": name,
        "description": description,
        "unit": unit,
        "gauge": {
            "dataPoints": datapoints,
        },
    }


def _datapoint(value: float | int | None, attributes: list[dict]) -> dict | None:
    """Build an OTLP datapoint. Returns None if value is None."""
    if value is None:
        return None
    now_ns = int(time.time() * 1e9)
    dp: dict[str, Any] = {
        "timeUnixNano": str(now_ns),
        "attributes": attributes,
    }
    if isinstance(value, float):
        dp["asDouble"] = value
    else:
        dp["asInt"] = str(value)
    return dp


def _session_attributes(session: dict) -> list[dict]:
    """Build OTLP attributes for a session."""
    return [
        {"key": "session_id", "value": {"stringValue": session.get("session_id", "unknown")}},
        {"key": "model", "value": {"stringValue": session.get("model_name") or "unknown"}},
        {
            "key": "project",
            "value": {"stringValue": session.get("project_dir") or session.get("workspace_dir") or "unknown"},
        },
    ]


def build_otlp_payload(sessions: list[dict]) -> dict:
    """Build complete OTLP/HTTP JSON payload from session data."""
    metrics_spec = [
        ("claude.session.cost", "Session cost", "usd", "cost_usd", float),
        ("claude.session.duration", "Session duration", "s", "duration_ms", "ms_to_s"),
        ("claude.session.api_duration", "API duration", "s", "api_duration_ms", "ms_to_s"),
        ("claude.session.lines_added", "Lines added", "lines", "lines_added", int),
        ("claude.session.lines_removed", "Lines removed", "lines", "lines_removed", int),
        ("claude.session.input_tokens", "Input tokens", "tokens", "total_input_tokens", int),
        ("claude.session.output_tokens", "Output tokens", "tokens", "total_output_tokens", int),
        ("claude.session.context_used", "Context used percentage", "percent", "used_percentage", float),
        ("claude.session.context_remaining", "Context remaining percentage", "percent", "remaining_percentage", float),
        ("claude.session.context_window_size", "Context window size", "tokens", "context_window_size", int),
        ("claude.session.current_input_tokens", "Current turn input tokens", "tokens", "current_input_tokens", int),
        ("claude.session.current_output_tokens", "Current turn output tokens", "tokens", "current_output_tokens", int),
        (
            "claude.session.cache_creation_tokens",
            "Cache creation input tokens",
            "tokens",
            "cache_creation_input_tokens",
            int,
        ),
        ("claude.session.cache_read_tokens", "Cache read input tokens", "tokens", "cache_read_input_tokens", int),
    ]

    otlp_metrics = []
    for name, desc, unit, field, dtype in metrics_spec:
        datapoints = []
        for s in sessions:
            attrs = _session_attributes(s)
            value = s.get(field)
            if value is not None:
                if dtype == "ms_to_s":
                    value = value / 1000.0
                dp = _datapoint(value, attrs)
                if dp:
                    datapoints.append(dp)
        if datapoints:
            otlp_metrics.append(_gauge_metric(name, desc, unit, datapoints))

    return {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "claude-code-metrics"}},
                        {"key": "service.version", "value": {"stringValue": "1.0.0"}},
                    ]
                },
                "scopeMetrics": [
                    {
                        "scope": {"name": "claude.statusline"},
                        "metrics": otlp_metrics,
                    }
                ],
            }
        ]
    }


async def push_otlp(sessions: list[dict]):
    """Push OTLP payload to configured endpoint. Fails silently."""
    if not config.OTLP_ENDPOINT:
        return
    payload = build_otlp_payload(sessions)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                config.OTLP_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code >= 400:
                logger.warning(f"OTLP push returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"OTLP push failed: {e}")
