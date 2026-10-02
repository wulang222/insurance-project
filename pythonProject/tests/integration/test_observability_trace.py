from __future__ import annotations

import time
from typing import Any, TypedDict

import pytest
from langgraph.graph import END, StateGraph
from langgraph.store.memory import InMemoryStore

from harness.runtime import RunManager
from observability.telemetry import Observability


class TraceState(TypedDict, total=False):
    messages: list[Any]
    route: str
    child_result: dict[str, Any]
    final_answer: str
    handled_by: list[str]


def _graph():
    async def complete(_state: TraceState) -> dict[str, Any]:
        start = time.perf_counter_ns()
        return {
            "route": "family_plan",
            "final_answer": "完成",
            "handled_by": ["profile_agent", "compliance_agent"],
            "child_result": {
                "plan": [{"task_id": "profile"}],
                "agent_trace": [
                    {
                        "agent": "profile_agent",
                        "status": "completed",
                        "started_at_ns": start,
                        "finished_at_ns": time.perf_counter_ns(),
                    },
                    {
                        "agent": "compliance_agent",
                        "status": "completed",
                        "started_at_ns": start,
                        "finished_at_ns": time.perf_counter_ns(),
                    },
                ],
            },
        }

    workflow = StateGraph(TraceState)
    workflow.add_node("complete", complete)
    workflow.set_entry_point("complete")
    workflow.add_edge("complete", END)
    return workflow.compile()


@pytest.mark.asyncio
async def test_run_exposes_route_plan_and_agent_spans() -> None:
    observability = Observability()
    runtime = RunManager(_graph(), InMemoryStore(), observability=observability)

    snapshot = await runtime.start("家庭保障规划", user_id="13800138000")

    assert snapshot.result is not None
    spans = snapshot.result.trace["spans"]
    names = {item["name"] for item in spans}
    assert {
        f"run {snapshot.run_id}",
        "route",
        "plan",
        "invoke_agent profile_agent",
        "invoke_agent compliance_agent",
    } <= names
    assert "13800138000" not in str(spans)
