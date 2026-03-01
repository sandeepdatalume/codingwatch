"""Prometheus text exposition format renderer."""

from datetime import datetime, timezone


def _label_str(session: dict) -> str:
    """Build Prometheus label string from a session row."""
    sid = (session.get("session_id") or "unknown")[:16]
    model = (session.get("model_name") or "unknown").replace('"', '\\"')
    project = (session.get("project_dir") or session.get("workspace_dir") or "unknown").replace('"', '\\"')
    return f'session_id="{sid}",model="{model}",project="{project}"'


def _gauge(name: str, help_text: str, entries: list[tuple[str, float | int | None]]) -> str:
    """Render a single gauge metric with multiple label sets."""
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} gauge"]
    for labels, value in entries:
        if value is not None:
            lines.append(f"{name}{{{labels}}} {value}")
    return "\n".join(lines)


def render_prometheus_metrics(sessions: list[dict]) -> str:
    """Render all sessions into Prometheus text format."""
    blocks: list[str] = []

    # Per-session metrics: (prometheus_name, help_text, db_field, transform)
    # transform: None=raw, "ms_to_s"=divide by 1000, "bool"=convert to 0/1
    metrics_spec = [
        ("claude_session_cost_usd", "Current session cost in USD", "cost_usd", None),
        ("claude_session_duration_seconds", "Session duration in seconds", "duration_ms", "ms_to_s"),
        ("claude_session_api_duration_seconds", "API call duration in seconds", "api_duration_ms", "ms_to_s"),
        ("claude_session_lines_added", "Lines added in session", "lines_added", None),
        ("claude_session_lines_removed", "Lines removed in session", "lines_removed", None),
        ("claude_session_input_tokens", "Total input tokens used", "total_input_tokens", None),
        ("claude_session_output_tokens", "Total output tokens used", "total_output_tokens", None),
        ("claude_session_context_used_pct", "Context window usage percentage", "used_percentage", None),
        ("claude_session_context_remaining_pct", "Context window remaining percentage", "remaining_percentage", None),
        ("claude_session_context_window_size", "Context window size", "context_window_size", None),
        ("claude_session_current_input_tokens", "Current turn input tokens", "current_input_tokens", None),
        ("claude_session_current_output_tokens", "Current turn output tokens", "current_output_tokens", None),
        ("claude_session_cache_creation_tokens", "Cache creation input tokens", "cache_creation_input_tokens", None),
        ("claude_session_cache_read_tokens", "Cache read input tokens", "cache_read_input_tokens", None),
        ("claude_session_exceeds_200k", "Whether session exceeds 200K context", "exceeds_200k_tokens", "bool"),
    ]

    for metric_name, help_text, field, transform in metrics_spec:
        entries = []
        for s in sessions:
            labels = _label_str(s)
            value = s.get(field)
            if transform == "ms_to_s" and value is not None:
                value = value / 1000.0
            elif transform == "bool" and value is not None:
                value = 1 if value else 0
            entries.append((labels, value))
        blocks.append(_gauge(metric_name, help_text, entries))

    # Aggregate metrics (no labels)
    now = datetime.now(timezone.utc)
    active_count = 0
    total_cost = 0.0
    for s in sessions:
        total_cost += s.get("cost_usd") or 0
        last_seen = s.get("last_seen")
        if last_seen:
            try:
                if isinstance(last_seen, str):
                    ls = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                else:
                    ls = last_seen
                if ls.tzinfo is None:
                    ls = ls.replace(tzinfo=timezone.utc)
                if (now - ls).total_seconds() < 600:
                    active_count += 1
            except (ValueError, TypeError):
                pass

    blocks.append(
        "# HELP claude_active_sessions_total Total number of active sessions\n"
        "# TYPE claude_active_sessions_total gauge\n"
        f"claude_active_sessions_total {active_count}"
    )
    blocks.append(
        "# HELP claude_total_cost_usd Aggregate cost across all sessions\n"
        "# TYPE claude_total_cost_usd gauge\n"
        f"claude_total_cost_usd {total_cost}"
    )

    return "\n".join(blocks) + "\n"
