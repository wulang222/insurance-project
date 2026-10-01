from __future__ import annotations

import asyncio

import pytest

from shared.memory import UserMemoryStore

from .conftest import build_runtime


@pytest.mark.anyio
async def test_two_threads_do_not_share_resume_payloads() -> None:
    runtime, _, _ = build_runtime()
    first, second = await asyncio.gather(
        runtime.start("用户一", user_id="user-1"),
        runtime.start("用户二", user_id="user-2"),
    )

    assert first.thread_id != second.thread_id

    second_done, first_done = await asyncio.gather(
        runtime.resume(second.run_id, {"age": 42}),
        runtime.resume(first.run_id, {"age": 23}),
    )
    first_after_resume = await runtime.get(first.run_id)

    assert first_after_resume.status == "completed"
    assert second_done.result is not None
    assert first_done.result is not None
    assert second_done.result.answer == "user=user-2;age=42"
    assert first_done.result.answer == "user=user-1;age=23"


@pytest.mark.anyio
async def test_two_users_do_not_share_long_term_profiles() -> None:
    _, _, store = build_runtime()
    memory = UserMemoryStore(store)

    await memory.save_user_profile("user-a", {"age": 28, "occupation": "程序员"})
    await memory.save_user_profile("user-b", {"age": 51, "occupation": "教师"})

    profile_a = await memory.load_user_profile("user-a")
    profile_b = await memory.load_user_profile("user-b")

    assert profile_a is not None
    assert profile_b is not None
    assert profile_a["age"] == 28
    assert profile_b["age"] == 51
    assert profile_a["occupation"] != profile_b["occupation"]
