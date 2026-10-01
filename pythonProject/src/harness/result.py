"""Serializable output contracts for agents and tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    """Evidence supporting one or more factual claims in an answer."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    source_version: str | None = None
    title: str | None = None
    locator: str | None = None
    quote: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RequiredInput(BaseModel):
    """Structured description of information needed to resume a run."""

    model_config = ConfigDict(extra="forbid")

    type: str = "input_required"
    fields: list[str] = Field(min_length=1)
    question: str = Field(min_length=1)
    prompt: str | None = None
    reason: str | None = None
    schema_: dict[str, Any] = Field(default_factory=dict, alias="schema")


class AgentResult(BaseModel):
    """Stable response envelope returned by every agent workflow."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: Literal["completed", "needs_input", "failed"]
    answer: str = ""
    handled_by: list[str] = Field(default_factory=list)
    structured_data: dict[str, Any] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    required_input: RequiredInput | None = None
    warnings: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None
    trace: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Stable response envelope returned by all business tools."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    data: Any | None = None
    source: str = Field(min_length=1)
    source_version: str | None = None
    latency_ms: int = Field(ge=0)
    cache_hit: bool = False
    warnings: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None
