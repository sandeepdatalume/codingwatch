from pydantic import BaseModel


class ModelInfo(BaseModel):
    id: str | None = None
    display_name: str | None = None


class WorkspaceInfo(BaseModel):
    current_dir: str | None = None
    project_dir: str | None = None


class CostInfo(BaseModel):
    total_cost_usd: float | None = 0.0
    total_duration_ms: int | None = 0
    total_api_duration_ms: int | None = 0
    total_lines_added: int | None = 0
    total_lines_removed: int | None = 0


class CurrentUsage(BaseModel):
    input_tokens: int | None = 0
    output_tokens: int | None = 0
    cache_creation_input_tokens: int | None = 0
    cache_read_input_tokens: int | None = 0


class ContextWindowInfo(BaseModel):
    total_input_tokens: int | None = 0
    total_output_tokens: int | None = 0
    context_window_size: int | None = None
    used_percentage: float | None = None
    remaining_percentage: float | None = None
    current_usage: CurrentUsage | None = None


class OutputStyleInfo(BaseModel):
    name: str | None = None


class VimInfo(BaseModel):
    mode: str | None = None


class AgentInfo(BaseModel):
    name: str | None = None


class MetricPayload(BaseModel):
    cwd: str | None = None
    session_id: str | None = None
    transcript_path: str | None = None
    model: ModelInfo | None = None
    workspace: WorkspaceInfo | None = None
    version: str | None = None
    output_style: OutputStyleInfo | None = None
    cost: CostInfo | None = None
    context_window: ContextWindowInfo | None = None
    exceeds_200k_tokens: bool | None = False
    vim: VimInfo | None = None
    agent: AgentInfo | None = None
