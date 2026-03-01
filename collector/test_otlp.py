"""Tests for OTLP payload builder."""

from collector.otlp import build_otlp_payload

MOCK_SESSION = {
    "session_id": "otlp-test-001",
    "model_name": "Opus",
    "project_dir": "/home/dev/myproject",
    "cost_usd": 0.05,
    "duration_ms": 60000,
    "api_duration_ms": 30000,
    "lines_added": 45,
    "lines_removed": 12,
    "total_input_tokens": 15234,
    "total_output_tokens": 4521,
    "used_percentage": 45.2,
    "remaining_percentage": 54.8,
    "context_window_size": 200000,
    "current_input_tokens": 8500,
    "current_output_tokens": 1200,
    "cache_creation_input_tokens": 5000,
    "cache_read_input_tokens": 2000,
}


def test_resource_attributes():
    payload = build_otlp_payload([MOCK_SESSION])
    rm = payload["resourceMetrics"][0]
    attrs = {a["key"]: a["value"]["stringValue"] for a in rm["resource"]["attributes"]}
    assert attrs["service.name"] == "claude-code-metrics"
    assert attrs["service.version"] == "1.0.0"


def test_scope_name():
    payload = build_otlp_payload([MOCK_SESSION])
    scope = payload["resourceMetrics"][0]["scopeMetrics"][0]["scope"]
    assert scope["name"] == "claude.statusline"


def test_all_metrics_present():
    payload = build_otlp_payload([MOCK_SESSION])
    metrics = payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
    names = {m["name"] for m in metrics}
    expected = {
        "claude.session.cost",
        "claude.session.duration",
        "claude.session.api_duration",
        "claude.session.lines_added",
        "claude.session.lines_removed",
        "claude.session.input_tokens",
        "claude.session.output_tokens",
        "claude.session.context_used",
        "claude.session.context_remaining",
        "claude.session.context_window_size",
        "claude.session.current_input_tokens",
        "claude.session.current_output_tokens",
        "claude.session.cache_creation_tokens",
        "claude.session.cache_read_tokens",
    }
    assert names == expected


def test_datapoint_attributes():
    payload = build_otlp_payload([MOCK_SESSION])
    metrics = payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
    dp = metrics[0]["gauge"]["dataPoints"][0]
    attr_keys = {a["key"] for a in dp["attributes"]}
    assert attr_keys == {"session_id", "model", "project"}


def test_duration_converted_to_seconds():
    payload = build_otlp_payload([MOCK_SESSION])
    metrics = payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
    duration_metric = next(m for m in metrics if m["name"] == "claude.session.duration")
    dp = duration_metric["gauge"]["dataPoints"][0]
    assert dp["asDouble"] == 60.0  # 60000ms -> 60s


def test_cache_metrics_values():
    payload = build_otlp_payload([MOCK_SESSION])
    metrics = payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
    cache_create = next(m for m in metrics if m["name"] == "claude.session.cache_creation_tokens")
    dp = cache_create["gauge"]["dataPoints"][0]
    assert dp["asInt"] == "5000"
    cache_read = next(m for m in metrics if m["name"] == "claude.session.cache_read_tokens")
    dp = cache_read["gauge"]["dataPoints"][0]
    assert dp["asInt"] == "2000"


def test_empty_sessions():
    payload = build_otlp_payload([])
    metrics = payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
    assert metrics == []


def test_none_values_excluded():
    session = {**MOCK_SESSION, "used_percentage": None, "remaining_percentage": None}
    payload = build_otlp_payload([session])
    metrics = payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
    names = {m["name"] for m in metrics}
    assert "claude.session.context_used" not in names
    assert "claude.session.context_remaining" not in names
