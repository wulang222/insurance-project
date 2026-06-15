"""Thin programmatic interface for the supervisor agent."""

from __future__ import annotations

import uuid
from typing import Any

from supervisor_agent.graph import build_graph


async def invoke_supervisor_agent(
    message: str,
    user_id: str | None = None,
    session_id: str | None = None,
    store: Any = None,
) -> dict:
    """Invoke the supervisor and return a stable dict for external callers."""
    graph = build_graph(store=store)
    thread_id = session_id or str(uuid.uuid4())

    config = {"configurable": {"thread_id": thread_id}}
    input_data = {"messages": [{"role": "user", "content": message}]}

    if user_id:
        config["configurable"]["user_id"] = user_id
        input_data["user_id"] = user_id

    result = await graph.ainvoke(input_data, config)

    return {
        "session_id": thread_id,
        "agent_type": "supervisor_agent",
        "handled_by": result.get("handled_by", ""),
        "route": result.get("route", ""),
        "route_reason": result.get("route_reason", ""),
        "content": result.get("final_answer", ""),
        "raw_result": result,
    }

