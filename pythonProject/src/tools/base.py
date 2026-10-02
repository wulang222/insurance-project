"""Contracts shared by every governed business tool."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolSpec(BaseModel):
    """Stable identity and policy metadata for a business capability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    risk_level: Literal["read", "write", "sensitive"]
    idempotent: bool
    timeout_seconds: float = Field(gt=0)
    required_scopes: list[str] = Field(default_factory=list)


class ToolCallContext(BaseModel):
    """Non-secret invocation identity and per-run policy inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    user_id: str | None = None
    scopes: frozenset[str] = Field(default_factory=frozenset)
    approved: bool = False
    max_tool_calls: int = Field(default=12, ge=0)
    max_model_calls: int = Field(default=8, ge=0)
    idempotency_key: str | None = None
    model_policy: str = "balanced"
    prompt_versions: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "ToolCallContext":
        values = (config or {}).get("configurable", {})
        return cls(
            request_id=str(values.get("request_id", "local-request")),
            run_id=str(values.get("run_id", values.get("thread_id", "local-run"))),
            user_id=values.get("user_id"),
            scopes=frozenset(values.get("scopes", ())),
            approved=bool(values.get("approved", False)),
            max_tool_calls=int(values.get("max_tool_calls", 12)),
            max_model_calls=int(values.get("max_model_calls", 8)),
            idempotency_key=values.get("idempotency_key"),
            model_policy=str(values.get("model_policy", "balanced")),
            prompt_versions=dict(values.get("prompt_versions", {})),
        )


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    spec: ToolSpec
    input_model: type[BaseModel]
    output_model: Any
    handler: Callable[..., Any]


class ToolAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    run_id: str
    tool_name: str
    tool_version: str
    duration_ms: int = Field(ge=0)
    status: Literal["ok", "denied", "invalid", "timeout", "failed", "budget_exceeded"]
    attempts: int = Field(ge=0)
    cache_hit: bool = False
