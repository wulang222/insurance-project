"""Freeze the legacy HTTP contract used by the Java portal."""

from __future__ import annotations

from fastapi.testclient import TestClient

import server


class FakeSupervisorGraph:
    async def ainvoke(self, input_data: dict, config: dict) -> dict:
        assert input_data["messages"][-1]["content"] == "你好"
        assert config["configurable"]["thread_id"] == "session-1"
        return {
            "final_answer": "您好，请问您想了解哪类保险问题？",
            "handled_by": "knowledge_agent",
            "route": "knowledge_agent",
            "route_reason": "contract-test stub",
        }


def test_legacy_chat_response_shape(
    monkeypatch,
    mocked_external_services: object,
) -> None:
    monkeypatch.setattr(server, "supervisor_graph", FakeSupervisorGraph())

    with TestClient(server.app) as client:
        response = client.post(
            "/chat",
            json={"session_id": "session-1", "user_id": "user-1", "message": "你好"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "session-1"
    assert payload["message_id"]
    assert payload["content"] == "您好，请问您想了解哪类保险问题？"
    assert payload["handled_by"] == "knowledge_agent"
    assert payload["route"] == "knowledge_agent"
    assert payload["route_reason"] == "contract-test stub"
