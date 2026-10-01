"""Unit tests for Day 1 harness contracts."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from harness.context import RunContext
from harness.errors import (
    AgentError,
    DependencyUnavailableError,
    ErrorCode,
    InvalidAgentOutputError,
    PolicyDeniedError,
    ToolExecutionError,
)
from harness.result import AgentResult, Citation, RequiredInput, ToolResult


def test_run_context_is_json_serializable_and_immutable() -> None:
    context = RunContext(
        request_id="request-1",
        run_id="run-1",
        thread_id="thread-1",
        user_id="user-1",
        prompt_version="supervisor.v1",
        model_policy="balanced",
    )

    assert json.loads(context.model_dump_json())["run_id"] == "run-1"
    with pytest.raises(ValidationError):
        context.run_id = "changed"  # type: ignore[misc]


def test_agent_result_is_json_serializable() -> None:
    result = AgentResult(
        status="needs_input",
        handled_by=["profile_agent"],
        required_input=RequiredInput(
            fields=["age", "budget"],
            prompt="请补充年龄和预算",
            schema={"age": {"type": "integer"}},
        ),
        citations=[Citation(source="mysql:insurance_products", locator="CI001")],
    )

    payload = json.loads(result.model_dump_json(by_alias=True))
    assert payload["status"] == "needs_input"
    assert payload["required_input"]["schema"]["age"]["type"] == "integer"
    assert payload["citations"][0]["source"] == "mysql:insurance_products"


def test_tool_result_is_json_serializable() -> None:
    result = ToolResult(
        ok=True,
        data={"product_id": "CI001"},
        source="mysql:insurance_products",
        source_version="42",
        latency_ms=12,
    )

    assert json.loads(result.model_dump_json())["data"]["product_id"] == "CI001"


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (AgentError("unexpected"), ErrorCode.INTERNAL_ERROR),
        (ToolExecutionError("bad input"), ErrorCode.TOOL_INVALID_ARGUMENTS),
        (
            ToolExecutionError("timeout", code=ErrorCode.TOOL_TIMEOUT),
            ErrorCode.TOOL_TIMEOUT,
        ),
        (
            DependencyUnavailableError("mysql unavailable"),
            ErrorCode.DEPENDENCY_UNAVAILABLE,
        ),
        (PolicyDeniedError("not allowed"), ErrorCode.POLICY_DENIED),
        (InvalidAgentOutputError("invalid json"), ErrorCode.MODEL_INVALID_OUTPUT),
    ],
)
def test_errors_have_stable_codes(
    error: AgentError,
    expected_code: ErrorCode,
) -> None:
    assert error.code is expected_code
    assert error.to_dict()["code"] == expected_code.value


def test_error_code_catalog_is_complete() -> None:
    assert {code.value for code in ErrorCode} == {
        "INPUT_REQUIRED",
        "DEPENDENCY_UNAVAILABLE",
        "TOOL_TIMEOUT",
        "TOOL_INVALID_ARGUMENTS",
        "MODEL_TIMEOUT",
        "MODEL_INVALID_OUTPUT",
        "POLICY_DENIED",
        "NO_BUSINESS_RESULT",
        "INTERNAL_ERROR",
    }
