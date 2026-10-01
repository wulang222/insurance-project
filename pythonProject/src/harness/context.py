"""Identity and execution-budget contract for a single agent run."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RunContext(BaseModel):
    """Immutable request metadata passed explicitly through the harness."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    user_id: str | None = None
    tenant_id: str = "default"
    locale: str = "zh-CN"
    prompt_version: str = Field(min_length=1)
    model_policy: str = Field(min_length=1)
    max_model_calls: int = Field(default=8, ge=0)
    max_tool_calls: int = Field(default=12, ge=0)
    timeout_seconds: int = Field(default=90, gt=0)
