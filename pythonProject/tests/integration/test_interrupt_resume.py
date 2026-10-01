from __future__ import annotations

import pytest

from .conftest import build_runtime


@pytest.mark.anyio
async def test_missing_age_interrupts_and_resumes_same_thread() -> None:
    runtime, _, _ = build_runtime()

    interrupted = await runtime.start("我是程序员", user_id="user-1")

    assert interrupted.status == "needs_input"
    assert interrupted.result is not None
    assert interrupted.result.required_input is not None
    assert interrupted.result.required_input.type == "missing_profile_fields"
    assert interrupted.result.required_input.fields == ["age"]

    resumed = await runtime.resume(interrupted.run_id, {"age": 28})

    assert resumed.status == "completed"
    assert resumed.thread_id == interrupted.thread_id
    assert resumed.result is not None
    assert resumed.result.answer == "user=user-1;age=28"
    assert resumed.result.trace["thread_id"] == interrupted.thread_id

    events = await runtime.get_events(interrupted.run_id)
    assert [event.type for event in events] == [
        "run.started",
        "run.interrupted",
        "run.resumed",
        "agent.completed",
        "run.completed",
    ]
