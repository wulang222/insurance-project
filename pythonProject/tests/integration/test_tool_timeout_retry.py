from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from harness.errors import ErrorCode, ToolExecutionError
from middleware.tool import ToolGateway
from tools.base import ToolCallContext, ToolDefinition, ToolSpec
from tools.registry import ToolRegistry


class Input(BaseModel):
    value: int


def make_gateway(handler, *, risk: str, idempotent: bool) -> ToolGateway:
    return ToolGateway(
        ToolRegistry(
            [
                ToolDefinition(
                    ToolSpec(
                        name="slow",
                        version="1",
                        description="slow tool",
                        risk_level=risk,
                        idempotent=idempotent,
                        timeout_seconds=0.01,
                        required_scopes=[],
                    ),
                    Input,
                    int,
                    handler,
                )
            ]
        )
    )


def context() -> ToolCallContext:
    return ToolCallContext(request_id="request", run_id="run")


@pytest.mark.asyncio
async def test_read_idempotent_tool_retries_after_timeout() -> None:
    calls = 0

    async def handler(value: int) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            await asyncio.sleep(0.03)
        return value

    gateway = make_gateway(handler, risk="read", idempotent=True)
    result = await gateway.execute("slow", {"value": 7}, context=context())
    assert result.data == 7
    assert calls == 2
    assert gateway.audit_events[-1].attempts == 2


@pytest.mark.asyncio
async def test_write_tool_never_retries_after_timeout() -> None:
    calls = 0

    async def handler(value: int) -> int:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.03)
        return value

    gateway = make_gateway(handler, risk="write", idempotent=False)
    with pytest.raises(ToolExecutionError) as error:
        await gateway.execute("slow", {"value": 7}, context=context())
    assert error.value.code is ErrorCode.TOOL_TIMEOUT
    assert calls == 1
