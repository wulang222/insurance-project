"""State definitions for the supervisor agent."""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages


AgentRoute = Literal["insurance_agent", "knowledge_agent", "crm_agent"]


class SupervisorAgentState(TypedDict, total=False):
    """Shared state for routing a user request to one child agent."""

    messages: Annotated[list, add_messages]
    user_id: str
    route: AgentRoute
    route_reason: str
    child_result: dict[str, Any]
    final_answer: str
    handled_by: str

