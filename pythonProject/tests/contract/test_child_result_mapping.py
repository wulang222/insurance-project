"""Freeze how child-agent state is mapped into the supervisor response."""

from __future__ import annotations

import pytest

import supervisor_agent.graph as supervisor_graph


class FakeChildGraph:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.last_input: dict | None = None
        self.last_config: dict | None = None

    async def ainvoke(self, input_data: dict, config: dict) -> dict:
        self.last_input = input_data
        self.last_config = config
        return self.result


@pytest.mark.anyio
async def test_insurance_child_result_mapping(
    monkeypatch: pytest.MonkeyPatch,
    mocked_external_services: object,
) -> None:
    child = FakeChildGraph({"final_recommendation": "推荐结果"})
    monkeypatch.setattr(supervisor_graph, "_get_insurance_graph", lambda: child)

    result = await supervisor_graph.call_insurance_agent_node(
        {
            "messages": [{"role": "user", "content": "想买重疾险"}],
            "user_id": "user-1",
        },
        {"configurable": {"thread_id": "thread-1", "user_id": "user-1"}},
    )

    assert result["handled_by"] == "insurance_agent"
    assert result["final_answer"] == "推荐结果"
    assert result["child_result"] == {"final_recommendation": "推荐结果"}
    assert child.last_config == {
        "configurable": {
            "thread_id": "thread-1:insurance_agent",
            "user_id": "user-1",
        }
    }


@pytest.mark.anyio
async def test_knowledge_child_result_mapping(
    monkeypatch: pytest.MonkeyPatch,
    mocked_external_services: object,
) -> None:
    child = FakeChildGraph({"final_answer": "等待期解释"})
    monkeypatch.setattr(supervisor_graph, "_get_knowledge_graph", lambda: child)

    result = await supervisor_graph.call_knowledge_agent_node(
        {"messages": [{"role": "user", "content": "等待期是什么"}]},
        {"configurable": {"thread_id": "thread-2"}},
    )

    assert result["handled_by"] == "knowledge_agent"
    assert result["final_answer"] == "等待期解释"


@pytest.mark.anyio
async def test_crm_child_result_mapping(
    monkeypatch: pytest.MonkeyPatch,
    mocked_external_services: object,
) -> None:
    child = FakeChildGraph({"crm_report": "CRM 报告"})
    monkeypatch.setattr(supervisor_graph, "_get_crm_graph", lambda: child)

    result = await supervisor_graph.call_crm_agent_node(
        {"messages": [{"role": "user", "content": "分析续保风险"}]},
        {"configurable": {"thread_id": "thread-3"}},
    )

    assert result["handled_by"] == "crm_agent"
    assert result["final_answer"] == "CRM 报告"
