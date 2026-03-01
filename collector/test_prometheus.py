"""Tests for Prometheus text format renderer."""

from collector.prometheus import render_prometheus_metrics

MOCK_SESSION = {
    "session_id": "abc123def456ghij",
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
    "exceeds_200k_tokens": False,
    "last_seen": "2099-01-01T00:00:00+00:00",  # Far future = active
}


def test_renders_all_per_session_metrics():
    text = render_prometheus_metrics([MOCK_SESSION])
    expected_metrics = [
        "claude_session_cost_usd",
        "claude_session_duration_seconds",
        "claude_session_api_duration_seconds",
        "claude_session_lines_added",
        "claude_session_lines_removed",
        "claude_session_input_tokens",
        "claude_session_output_tokens",
        "claude_session_context_used_pct",
        "claude_session_context_remaining_pct",
        "claude_session_context_window_size",
        "claude_session_current_input_tokens",
        "claude_session_current_output_tokens",
        "claude_session_cache_creation_tokens",
        "claude_session_cache_read_tokens",
        "claude_session_exceeds_200k",
    ]
    for name in expected_metrics:
        assert f"# HELP {name}" in text, f"Missing HELP for {name}"
        assert f"# TYPE {name} gauge" in text, f"Missing TYPE for {name}"


def test_label_format():
    text = render_prometheus_metrics([MOCK_SESSION])
    assert 'session_id="abc123def456ghij"' in text
    assert 'model="Opus"' in text
    assert 'project="/home/dev/myproject"' in text


def test_duration_converted_to_seconds():
    text = render_prometheus_metrics([MOCK_SESSION])
    lines = [line for line in text.split("\n") if line.startswith("claude_session_duration_seconds{")]
    assert len(lines) == 1
    assert "60.0" in lines[0]


def test_exceeds_200k_is_0_or_1():
    text = render_prometheus_metrics([MOCK_SESSION])
    lines = [line for line in text.split("\n") if line.startswith("claude_session_exceeds_200k{")]
    assert len(lines) == 1
    assert lines[0].endswith(" 0")


def test_cache_metrics_rendered():
    text = render_prometheus_metrics([MOCK_SESSION])
    lines = [line for line in text.split("\n") if line.startswith("claude_session_cache_creation_tokens{")]
    assert len(lines) == 1
    assert "5000" in lines[0]
    lines = [line for line in text.split("\n") if line.startswith("claude_session_cache_read_tokens{")]
    assert len(lines) == 1
    assert "2000" in lines[0]


def test_aggregate_metrics():
    text = render_prometheus_metrics([MOCK_SESSION])
    assert "claude_active_sessions_total 1" in text
    assert "claude_total_cost_usd 0.05" in text


def test_empty_sessions():
    text = render_prometheus_metrics([])
    assert "claude_active_sessions_total 0" in text
    assert "claude_total_cost_usd 0.0" in text
    assert "# HELP claude_session_cost_usd" in text


def test_multiple_sessions():
    s1 = {**MOCK_SESSION, "session_id": "session-aaa", "cost_usd": 0.10}
    s2 = {**MOCK_SESSION, "session_id": "session-bbb", "cost_usd": 0.20}
    text = render_prometheus_metrics([s1, s2])
    assert "claude_total_cost_usd 0.3" in text
    assert 'session_id="session-aaa"' in text
    assert 'session_id="session-bbb"' in text
