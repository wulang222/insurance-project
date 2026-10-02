from __future__ import annotations

import pytest

from evals.replay import compare_records

from .conftest import build_runtime


@pytest.mark.asyncio
async def test_replay_reuses_input_resume_payload_and_overrides_policy() -> None:
    runtime, _, _ = build_runtime()
    interrupted = await runtime.start("我需要保障", user_id="replay-user")
    completed = await runtime.resume(interrupted.run_id, {"age": 31})

    replayed = await runtime.replay(
        completed.run_id,
        prompt_version="recommendation:v2",
        model_policy="cheap",
    )
    source_record = await runtime.get_record(completed.run_id)
    replay_record = await runtime.get_record(replayed.run_id)
    comparison = compare_records(source_record, replay_record)

    assert replayed.status == "completed"
    assert replayed.result is not None
    assert replayed.result.answer == completed.result.answer
    assert replay_record.parent_run_id == completed.run_id
    assert replay_record.context.prompt_version == "recommendation:v2"
    assert replay_record.context.model_policy == "cheap"
    assert comparison.final_answer["source"] == comparison.final_answer["replay"]
