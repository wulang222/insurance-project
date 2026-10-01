"""Explicit dependency container for one agent definition or run."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore


LLMFactory = Callable[..., Any]


class ToolGateway(Protocol):
    """Minimal contract required from the Day 3 tool gateway."""

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> Any: ...


class PromptRegistry(Protocol):
    """Minimal contract required from the Day 3 prompt registry."""

    def get(self, name: str, version: str) -> Any: ...


class Tracer(Protocol):
    """Tracing boundary used without coupling agents to a vendor SDK."""

    def start_span(self, name: str, **attributes: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class AgentDependencies:
    """Initialized runtime dependencies passed explicitly to agents."""

    llm_factory: LLMFactory
    checkpointer: BaseCheckpointSaver
    store: BaseStore
    tool_gateway: ToolGateway | None = None
    prompt_registry: PromptRegistry | None = None
    tracer: Tracer | None = None
    mysql_client: Any | None = None
    milvus_client: Any | None = None
