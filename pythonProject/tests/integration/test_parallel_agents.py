from __future__ import annotations

import asyncio

import pytest

from harness.result import ToolResult
from .test_family_plan_graph import FamilyToolGateway, build_graph, config


class DelayedGateway(FamilyToolGateway):
    async def execute(self, tool_name, arguments, *, context):
        if tool_name in {
            "extract_customer_profile",
            "get_customer_policy_portfolio",
            "search_active_insurance_products",
            "retrieve_policy_evidence",
        }:
            await asyncio.sleep(0.03)
        result: ToolResult = await super().execute(
            tool_name,
            arguments,
            context=context,
        )
        return result


def overlaps(left: dict, right: dict) -> bool:
    return (
        left["started_at_ns"] < right["finished_at_ns"]
        and right["started_at_ns"] < left["finished_at_ns"]
    )


@pytest.mark.asyncio
async def test_independent_specialists_run_in_two_parallel_waves() -> None:
    result = await build_graph(DelayedGateway()).ainvoke(
        {"messages": [{"role": "user", "content": "35岁程序员做家庭保障规划"}]},
        config("parallel"),
    )
    traces = {item["agent"]: item for item in result["agent_trace"]}

    assert overlaps(traces["profile_agent"], traces["crm_agent"])
    assert overlaps(traces["product_agent"], traces["knowledge_agent"])
    assert traces["coverage_gap_agent"]["started_at_ns"] >= max(
        traces["profile_agent"]["finished_at_ns"],
        traces["crm_agent"]["finished_at_ns"],
    )
    assert traces["compliance_agent"]["started_at_ns"] >= traces["aggregate"]["finished_at_ns"]
