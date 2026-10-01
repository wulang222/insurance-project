from __future__ import annotations

import pytest
from pydantic import BaseModel

from harness.errors import PolicyDeniedError
from middleware.tool import ToolGateway
from tools.base import ToolCallContext, ToolDefinition, ToolSpec
from tools.registry import ToolRegistry


class Input(BaseModel):
    value: int


@pytest.mark.asyncio
async def test_authorization_is_fail_closed() -> None:
    calls = 0

    def handler(value: int) -> int:
        nonlocal calls
        calls += 1
        return value

    gateway = ToolGateway(
        ToolRegistry(
            [
                ToolDefinition(
                    ToolSpec(
                        name="protected",
                        version="1",
                        description="protected tool",
                        risk_level="read",
                        idempotent=True,
                        timeout_seconds=1,
                        required_scopes=["products:read"],
                    ),
                    Input,
                    int,
                    handler,
                )
            ]
        )
    )
    with pytest.raises(PolicyDeniedError):
        await gateway.execute(
            "protected",
            {"value": 1},
            context=ToolCallContext(request_id="request", run_id="run"),
        )
    assert calls == 0
    assert gateway.audit_events[-1].status == "denied"
