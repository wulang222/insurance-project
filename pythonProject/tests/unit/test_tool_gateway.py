from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from harness.errors import DependencyUnavailableError, PolicyDeniedError, ToolExecutionError
from middleware.tool import ToolGateway
from tools.base import ToolCallContext, ToolDefinition, ToolSpec
from tools.product_tools import FakeProductRepository, ProductSearchInput
from tools.registry import ToolRegistry


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int


class Output(BaseModel):
    value: int


def definition(handler, *, risk="read", idempotent=True) -> ToolDefinition:
    return ToolDefinition(
        ToolSpec(
            name="sample",
            version="1.2.3",
            description="sample tool",
            risk_level=risk,
            idempotent=idempotent,
            timeout_seconds=1,
            required_scopes=["sample:read"],
        ),
        Input,
        Output,
        handler,
    )


def context(**changes) -> ToolCallContext:
    values = {
        "request_id": "request-1",
        "run_id": "run-1",
        "scopes": frozenset({"sample:read"}),
        "max_tool_calls": 2,
    }
    values.update(changes)
    return ToolCallContext(**values)


@pytest.mark.asyncio
async def test_argument_validation_happens_before_handler() -> None:
    calls = 0

    def handler(value: int) -> Output:
        nonlocal calls
        calls += 1
        return Output(value=value)

    gateway = ToolGateway(ToolRegistry([definition(handler)]))
    with pytest.raises(ToolExecutionError):
        await gateway.execute("sample", {"value": "bad"}, context=context())

    assert calls == 0
    assert gateway.audit_events[-1].status == "invalid"


@pytest.mark.asyncio
async def test_empty_success_is_distinct_from_dependency_failure() -> None:
    class EmptyInput(BaseModel):
        pass

    registry = ToolRegistry(
        [
            ToolDefinition(
                ToolSpec(
                    name="empty",
                    version="1",
                    description="empty search",
                    risk_level="read",
                    idempotent=True,
                    timeout_seconds=1,
                    required_scopes=[],
                ),
                EmptyInput,
                list[int],
                lambda: [],
            )
        ]
    )
    gateway = ToolGateway(registry)
    result = await gateway.execute("empty", {}, context=context(scopes=frozenset()))
    assert result.ok is True
    assert result.data == []

    def unavailable() -> list[int]:
        raise DependencyUnavailableError("db down")

    failure_gateway = ToolGateway(
        ToolRegistry(
            [
                ToolDefinition(
                    registry.get("empty").spec.model_copy(update={"name": "failure"}),
                    EmptyInput,
                    list[int],
                    unavailable,
                )
            ]
        )
    )
    with pytest.raises(DependencyUnavailableError):
        await failure_gateway.execute("failure", {}, context=context(scopes=frozenset()))


@pytest.mark.asyncio
async def test_tool_budget_ends_run_early() -> None:
    gateway = ToolGateway(ToolRegistry([definition(lambda value: Output(value=value))]))
    limited = context(max_tool_calls=1)
    await gateway.execute("sample", {"value": 1}, context=limited)
    with pytest.raises(PolicyDeniedError, match="budget"):
        await gateway.execute("sample", {"value": 2}, context=limited)
    assert gateway.audit_events[-1].status == "budget_exceeded"


def test_fake_product_repository_matches_all_occupations_but_not_inactive() -> None:
    repository = FakeProductRepository(
        [
            {
                "product_id": "active",
                "product_name": "全民产品",
                "insurance_type": "医疗险",
                "target_occupations": "全部职业",
                "is_active": 1,
            },
            {
                "product_id": "inactive",
                "product_name": "停售产品",
                "insurance_type": "医疗险",
                "target_occupations": "全部职业",
                "is_active": 0,
            },
        ]
    )
    rows = repository.search_active(
        ProductSearchInput(insurance_type="医疗险", occupation="高空作业")
    )
    assert [row["product_id"] for row in rows] == ["active"]
