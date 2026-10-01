"""Freeze the current supervisor routing behavior before refactoring it."""

from __future__ import annotations

import pytest

from supervisor_agent.graph import route_request_node


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("message", "expected_route"),
    [
        ("28 岁程序员预算 5000 想买重疾险", "insurance_agent"),
        ("等待期是什么意思", "knowledge_agent"),
        ("分析客户流失与续保风险", "crm_agent"),
        ("你好", "knowledge_agent"),
    ],
)
async def test_current_route_contract(
    message: str,
    expected_route: str,
    mocked_external_services: object,
) -> None:
    result = await route_request_node(
        {"messages": [{"role": "user", "content": message}]}
    )

    assert result["route"] == expected_route
    assert result["route_reason"]
