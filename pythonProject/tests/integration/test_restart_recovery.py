from __future__ import annotations

import pytest

from .conftest import build_runtime


@pytest.mark.anyio
async def test_new_runtime_recovers_interrupted_run() -> None:
    first_runtime, checkpointer, store = build_runtime()
    interrupted = await first_runtime.start("需要保障", user_id="user-restart")

    assert interrupted.status == "needs_input"

    # 模拟 Python 服务重建：丢弃 RunManager/Graph，保留持久化后端。
    restarted_runtime, _, _ = build_runtime(checkpointer, store)
    restored = await restarted_runtime.get(interrupted.run_id)
    resumed = await restarted_runtime.resume(interrupted.run_id, {"age": 36})

    assert restored.status == "needs_input"
    assert restored.thread_id == interrupted.thread_id
    assert resumed.status == "completed"
    assert resumed.result is not None
    assert resumed.result.answer == "user=user-restart;age=36"
