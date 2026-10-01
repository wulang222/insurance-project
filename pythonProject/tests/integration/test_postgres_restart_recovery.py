from __future__ import annotations

import os

import pytest

from harness.runtime import RunManager
from infrastructure.postgres import PostgresSettings, open_postgres_resources

from .conftest import build_resume_graph


@pytest.mark.anyio
async def test_postgres_recovers_run_after_resources_are_reopened() -> None:
    uri = os.getenv("TEST_POSTGRES_URI", "").strip()
    if not uri:
        pytest.skip("TEST_POSTGRES_URI is required for the PostgreSQL recovery test")

    settings = PostgresSettings(uri=uri)
    async with open_postgres_resources(settings) as first_resources:
        first_graph = build_resume_graph(first_resources.checkpointer)
        first_runtime = RunManager(first_graph, first_resources.store)
        interrupted = await first_runtime.start(
            "需要保障",
            user_id="postgres-restart-user",
        )
        assert interrupted.status == "needs_input"

    # 关闭并重建连接、Checkpointer、Store、Graph 与 RunManager。
    async with open_postgres_resources(settings) as restarted_resources:
        restarted_graph = build_resume_graph(restarted_resources.checkpointer)
        restarted_runtime = RunManager(restarted_graph, restarted_resources.store)
        restored = await restarted_runtime.get(interrupted.run_id)
        completed = await restarted_runtime.resume(interrupted.run_id, {"age": 47})

    assert restored.status == "needs_input"
    assert restored.thread_id == interrupted.thread_id
    assert completed.status == "completed"
    assert completed.result is not None
    assert completed.result.answer == "user=postgres-restart-user;age=47"
