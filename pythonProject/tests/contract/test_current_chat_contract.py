"""Freeze the legacy HTTP contract used by the Java portal."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

import server
from harness.result import AgentResult
from harness.runtime import RunSnapshot


class FakeRuntime:
    async def start(
        self,
        message: str,
        *,
        user_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ) -> RunSnapshot:
        assert message == "你好"
        assert user_id == "user-1"
        assert thread_id == "session-1"
        return RunSnapshot(
            request_id=request_id or "request-1",
            run_id="run-1",
            thread_id=thread_id,
            status="completed",
            result=AgentResult(
                status="completed",
                answer="您好，请问您想了解哪类保险问题？",
                handled_by=["knowledge_agent"],
                structured_data={
                    "route": "knowledge_agent",
                    "route_reason": "contract-test stub",
                },
            ),
        )


@asynccontextmanager
async def fake_lifespan(app):
    app.state.runtime = FakeRuntime()
    yield


def test_legacy_chat_response_shape(
    monkeypatch,
    mocked_external_services: object,
) -> None:
    app = server.create_app(lifespan=fake_lifespan)

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"session_id": "session-1", "user_id": "user-1", "message": "你好"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "session-1"
    assert payload["message_id"] == "run-1"
    assert payload["content"] == "您好，请问您想了解哪类保险问题？"
    assert payload["handled_by"] == "knowledge_agent"
    assert payload["route"] == "knowledge_agent"
    assert payload["route_reason"] == "contract-test stub"
