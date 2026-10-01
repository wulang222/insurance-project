from __future__ import annotations

from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

import insurance_agent.graph as insurance_graph
from harness.runtime import RunManager
from shared.memory import UserMemoryStore


@pytest.mark.anyio
async def test_insurance_graph_uses_structured_interrupt_and_saves_resumed_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_extract(arguments: dict) -> dict:
        conversation = arguments["conversation"]
        return {
            "age": 28 if "用户补充信息" in conversation else None,
            "occupation": "程序员",
            "budget": 5000,
            "insurance_type": "重疾险",
        }

    monkeypatch.setattr(
        insurance_graph,
        "query_insurance_products_mysql",
        SimpleNamespace(invoke=lambda _arguments: []),
    )
    monkeypatch.setattr(
        insurance_graph,
        "extract_user_profile",
        SimpleNamespace(invoke=fake_extract),
    )

    checkpointer = MemorySaver()
    store = InMemoryStore()
    graph = insurance_graph.build_graph(checkpointer=checkpointer, store=store)
    runtime = RunManager(graph, store)

    interrupted = await runtime.start(
        "我是程序员，预算5000，想买重疾险",
        user_id="insurance-user",
    )

    assert interrupted.status == "needs_input"
    assert interrupted.result is not None
    assert interrupted.result.required_input is not None
    assert interrupted.result.required_input.type == "missing_profile_fields"
    assert interrupted.result.required_input.fields == ["age"]

    completed = await runtime.resume(interrupted.run_id, {"age": 28})

    assert completed.status == "completed"
    assert completed.result is not None
    assert "暂未找到完全匹配" in completed.result.answer

    stored = await UserMemoryStore(store).load_user_profile("insurance-user")
    assert stored is not None
    assert stored["age"] == 28
    assert stored["occupation"] == "程序员"
