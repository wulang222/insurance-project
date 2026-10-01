from __future__ import annotations

from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.store.memory import InMemoryStore

from harness.errors import DependencyUnavailableError
from harness.runtime import RunManager


class FailureState(TypedDict, total=False):
    messages: list


@pytest.mark.anyio
async def test_dependency_failure_is_not_reported_as_empty_business_result() -> None:
    async def fail_mysql(_state: FailureState) -> dict:
        raise DependencyUnavailableError(
            "MySQL is unavailable",
            details={"dependency": "mysql"},
            retryable=True,
        )

    workflow = StateGraph(FailureState)
    workflow.add_node("fail_mysql", fail_mysql)
    workflow.set_entry_point("fail_mysql")
    workflow.add_edge("fail_mysql", END)
    graph = workflow.compile(checkpointer=MemorySaver())
    runtime = RunManager(graph, InMemoryStore())

    failed = await runtime.start("查询保险产品")

    assert failed.status == "failed"
    assert failed.result is not None
    assert failed.result.error == {
        "code": "DEPENDENCY_UNAVAILABLE",
        "message": "MySQL is unavailable",
        "details": {"dependency": "mysql"},
        "retryable": True,
    }
