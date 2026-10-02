from __future__ import annotations

from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

import insurance_agent.graph as insurance_graph
from harness.dependencies import AgentDependencies
from harness.result import ToolResult
from supervisor_agent.graph import build_graph


class FakeToolGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(self, tool_name, arguments, **kwargs):
        del kwargs
        self.calls.append(tool_name)
        data = {
            "extract_customer_profile": {
                "age": 28,
                "occupation": "程序员",
                "budget": 5000,
                "insurance_type": "重疾险",
            },
            "search_active_insurance_products": [
                {
                    "product_id": "CI001",
                    "product_name": "测试重疾险",
                    "insurance_type": "重疾险",
                    "min_age": 18,
                    "max_age": 55,
                    "min_price": 3000,
                    "max_price": 8000,
                    "target_occupations": "全部职业",
                    "description": "测试产品",
                }
            ],
            "retrieve_policy_evidence": [
                {
                    "content": "等待期90天",
                    "source": "policy.pdf",
                    "score": 0.9,
                    "product_id": "CI001",
                }
            ],
            "save_profile_memory": {"saved": True},
        }[tool_name]
        return ToolResult(
            ok=True,
            data=data,
            source=tool_name,
            source_version="1",
            latency_ms=1,
        )


class FakeModelGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def invoke(self, request, **kwargs):
        del kwargs
        self.calls.append(request.prompt_id)
        return SimpleNamespace(data="基于在售产品与条款证据生成的推荐")


@pytest.mark.asyncio
async def test_core_recommendation_chain_uses_only_governed_gateways(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        del args, kwargs
        raise AssertionError("legacy raw adapter must not be called")

    monkeypatch.setattr(
        insurance_graph,
        "extract_user_profile",
        SimpleNamespace(invoke=forbidden),
    )
    monkeypatch.setattr(
        insurance_graph,
        "query_insurance_products_mysql",
        SimpleNamespace(invoke=forbidden),
    )
    monkeypatch.setattr(
        insurance_graph,
        "rag_enrich_products",
        SimpleNamespace(invoke=forbidden),
    )

    checkpointer = MemorySaver()
    store = InMemoryStore()
    tools = FakeToolGateway()
    models = FakeModelGateway()
    dependencies = AgentDependencies(
        llm_factory=forbidden,
        checkpointer=checkpointer,
        store=store,
        tool_gateway=tools,
        model_gateway=models,
    )
    graph = build_graph(
        checkpointer=checkpointer,
        store=store,
        dependencies=dependencies,
    )
    result = await graph.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "我28岁，是程序员，预算5000，想买重疾险",
                }
            ],
            "user_id": "user-1",
        },
        {
            "configurable": {
                "thread_id": "thread-1",
                "run_id": "run-1",
                "request_id": "request-1",
                "scopes": ["insurance:read", "knowledge:read", "memory:write"],
            }
        },
    )

    assert result["final_answer"] == "基于在售产品与条款证据生成的推荐"
    assert tools.calls == [
        "extract_customer_profile",
        "search_active_insurance_products",
        "retrieve_policy_evidence",
        "save_profile_memory",
    ]
    assert models.calls == ["recommendation.generate"]
