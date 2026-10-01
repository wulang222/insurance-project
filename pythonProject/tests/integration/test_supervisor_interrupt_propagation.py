from __future__ import annotations

from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import interrupt

import supervisor_agent.graph as supervisor_graph
from harness.runtime import RunManager


class ChildState(TypedDict, total=False):
    messages: list
    user_id: str
    final_recommendation: str


def build_interrupting_child(checkpointer: MemorySaver):
    async def collect_age(state: ChildState) -> dict:
        payload = interrupt(
            {
                "type": "missing_profile_fields",
                "fields": ["age"],
                "question": "请补充年龄",
            }
        )
        return {"final_recommendation": f"已收到年龄 {payload['age']}"}

    workflow = StateGraph(ChildState)
    workflow.add_node("collect_age", collect_age)
    workflow.set_entry_point("collect_age")
    workflow.add_edge("collect_age", END)
    return workflow.compile(checkpointer=checkpointer)


class UnusedChild:
    async def ainvoke(self, input_data, config):
        raise AssertionError("unexpected child route")


@pytest.mark.anyio
async def test_supervisor_propagates_and_resumes_child_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpointer = MemorySaver()
    store = InMemoryStore()
    insurance_child = build_interrupting_child(checkpointer)
    monkeypatch.setattr(
        supervisor_graph,
        "_get_insurance_graph",
        lambda **_: insurance_child,
    )
    monkeypatch.setattr(
        supervisor_graph,
        "_get_knowledge_graph",
        lambda **_: UnusedChild(),
    )
    monkeypatch.setattr(
        supervisor_graph,
        "_get_crm_graph",
        lambda **_: UnusedChild(),
    )

    graph = supervisor_graph.build_graph(checkpointer=checkpointer, store=store)
    runtime = RunManager(graph, store)
    interrupted = await runtime.start("我想买保险，预算5000", user_id="nested-user")

    assert interrupted.status == "needs_input"

    completed = await runtime.resume(interrupted.run_id, {"age": 29})

    assert completed.status == "completed"
    assert completed.result is not None
    assert completed.result.handled_by == ["insurance_agent"]
    assert completed.result.answer == "已收到年龄 29"
