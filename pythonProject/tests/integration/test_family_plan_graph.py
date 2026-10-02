from __future__ import annotations

from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from harness.dependencies import AgentDependencies
from harness.errors import DependencyUnavailableError
from harness.registry import build_agent_registry
from harness.result import ToolResult
from supervisor_agent.graph import build_graph as build_supervisor_graph
from workflows.family_plan import build_family_plan_graph


PRODUCT = {
    "product_id": "CI001",
    "product_name": "测试重疾险",
    "insurance_type": "重疾险",
    "min_age": 18,
    "max_age": 55,
    "min_price": 3000,
    "max_price": 8000,
    "target_occupations": "全部职业",
    "description": "仅用于测试",
}


class FamilyToolGateway:
    def __init__(
        self,
        *,
        age: int | None = 35,
        portfolio: list[dict[str, Any]] | None = None,
        fail_crm: bool = False,
        fail_products: bool = False,
        fail_knowledge: bool = False,
    ) -> None:
        self.age = age
        self.portfolio = portfolio or []
        self.fail_crm = fail_crm
        self.fail_products = fail_products
        self.fail_knowledge = fail_knowledge
        self.calls: list[str] = []

    async def execute(self, tool_name, arguments, *, context):
        del arguments, context
        self.calls.append(tool_name)
        if tool_name == "get_customer_policy_portfolio" and self.fail_crm:
            raise DependencyUnavailableError("crm down")
        if tool_name == "search_active_insurance_products" and self.fail_products:
            raise DependencyUnavailableError("mysql down")
        if tool_name == "retrieve_policy_evidence" and self.fail_knowledge:
            raise DependencyUnavailableError("milvus down")
        data = {
            "extract_customer_profile": {
                "age": self.age,
                "occupation": "程序员",
                "budget": 6000,
                "insurance_type": "重疾险",
            },
            "get_customer_policy_portfolio": {
                "profile": {},
                "policies": self.portfolio,
                "interactions": [],
            },
            "calculate_coverage_gap": {
                "covered_types": [],
                "missing_types": ["重疾险", "医疗险", "意外险", "寿险"],
            },
            "search_active_insurance_products": [PRODUCT],
            "retrieve_policy_evidence": [
                {
                    "content": "测试条款证据",
                    "source": "policy.pdf",
                    "score": 0.9,
                    "product_id": "CI001",
                }
            ],
        }[tool_name]
        return ToolResult(
            ok=True,
            data=data,
            source=tool_name,
            source_version="1",
            latency_ms=1,
        )


def build_graph(gateway: FamilyToolGateway):
    checkpointer = MemorySaver()
    store = InMemoryStore()
    dependencies = AgentDependencies(
        llm_factory=lambda **_: None,
        checkpointer=checkpointer,
        store=store,
        tool_gateway=gateway,
        agent_registry=build_agent_registry(),
    )
    return build_family_plan_graph(
        dependencies=dependencies,
        registry=dependencies.agent_registry,
        checkpointer=checkpointer,
        store=store,
    )


def config(thread_id: str = "family-thread") -> dict:
    return {
        "configurable": {
            "thread_id": thread_id,
            "run_id": f"run-{thread_id}",
            "request_id": f"request-{thread_id}",
            "scopes": ["insurance:read", "crm:read", "knowledge:read"],
        }
    }


@pytest.mark.asyncio
async def test_complete_profile_with_existing_medical_policy() -> None:
    gateway = FamilyToolGateway(
        portfolio=[
            {
                "policy_id": "P1",
                "insurance_type": "医疗险",
                "insured_amount": 2_000_000,
                "status": "active",
            }
        ]
    )
    result = await build_graph(gateway).ainvoke(
        {"messages": [{"role": "user", "content": "35岁程序员做家庭保障规划"}]},
        config(),
    )
    medical = next(item for item in result["coverage_gaps"] if item["category"] == "medical")
    assert medical["current_coverage"] == 2_000_000
    assert medical["gap"] == 0
    assert result["compliance"]["approved"] is True
    assert len(result["handled_by"]) == 6


@pytest.mark.asyncio
async def test_no_existing_policy_creates_all_configured_gaps() -> None:
    result = await build_graph(FamilyToolGateway()).ainvoke(
        {"messages": [{"role": "user", "content": "35岁做全家保险方案"}]},
        config("no-policy"),
    )
    assert len(result["coverage_gaps"]) == 4
    assert all(item["gap"] > 0 for item in result["coverage_gaps"])
    assert "不构成核保结论或正式保险建议" in result["disclaimer"]


@pytest.mark.asyncio
async def test_missing_age_interrupts_and_resumes() -> None:
    graph = build_graph(FamilyToolGateway(age=None))
    run_config = config("missing-age")
    interrupted = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "帮我做家庭保障规划"}]},
        run_config,
    )
    assert interrupted["__interrupt__"][0].value["fields"] == ["age"]

    completed = await graph.ainvoke(Command(resume={"age": 42}), run_config)
    assert completed["profile"]["age"] == 42
    assert completed["final_answer"]


@pytest.mark.asyncio
async def test_crm_failure_degrades_but_plan_completes() -> None:
    result = await build_graph(FamilyToolGateway(fail_crm=True)).ainvoke(
        {"messages": [{"role": "user", "content": "35岁做家庭保障规划"}]},
        config("crm-down"),
    )
    assert result["final_answer"]
    assert result["crm_available"] is False
    assert any("CRM 数据暂不可用" in warning for warning in result["warnings"])
    crm_trace = next(item for item in result["agent_trace"] if item["agent"] == "crm_agent")
    assert crm_trace["status"] == "degraded"


@pytest.mark.asyncio
async def test_product_database_failure_aborts_without_fabrication() -> None:
    graph = build_graph(FamilyToolGateway(fail_products=True))
    with pytest.raises(DependencyUnavailableError, match="mysql down"):
        await graph.ainvoke(
            {"messages": [{"role": "user", "content": "35岁做家庭保障规划"}]},
            config("product-down"),
        )


@pytest.mark.asyncio
async def test_knowledge_failure_adds_warning_without_fake_evidence() -> None:
    result = await build_graph(FamilyToolGateway(fail_knowledge=True)).ainvoke(
        {"messages": [{"role": "user", "content": "35岁做家庭保障规划"}]},
        config("knowledge-down"),
    )
    assert result["evidence"] == []
    assert any("不生成伪造条款或引用" in warning for warning in result["warnings"])
    assert "暂无可验证条款证据" in result["final_answer"]


@pytest.mark.asyncio
async def test_supervisor_routes_family_request_into_composable_graph() -> None:
    checkpointer = MemorySaver()
    store = InMemoryStore()
    gateway = FamilyToolGateway()
    dependencies = AgentDependencies(
        llm_factory=lambda **_: None,
        checkpointer=checkpointer,
        store=store,
        tool_gateway=gateway,
        agent_registry=build_agent_registry(),
    )
    graph = build_supervisor_graph(
        checkpointer=checkpointer,
        store=store,
        dependencies=dependencies,
    )
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "35岁程序员做家庭保障规划"}]},
        config("supervisor-family"),
    )
    assert result["route"] == "family_plan"
    assert result["final_answer"].startswith("## 家庭保障规划")
    assert len(result["handled_by"]) == 6
