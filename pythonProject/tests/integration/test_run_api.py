from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

import server

from .conftest import build_runtime


def test_run_api_interrupt_status_resume_and_events() -> None:
    runtime, _, _ = build_runtime()

    @asynccontextmanager
    async def lifespan(app):
        app.state.runtime = runtime
        yield

    app = server.create_app(lifespan=lifespan)
    with TestClient(app) as client:
        created = client.post(
            "/v1/runs",
            json={"message": "我需要保障", "user_id": "api-user"},
        )
        assert created.status_code == 200
        interrupted = created.json()
        assert interrupted["status"] == "needs_input"
        assert interrupted["required_input"] == {
            "type": "missing_profile_fields",
            "fields": ["age"],
            "question": "请补充年龄",
            "prompt": "请补充年龄",
            "schema": {},
        }

        queried = client.get(f"/v1/runs/{interrupted['run_id']}")
        assert queried.status_code == 200
        assert queried.json()["thread_id"] == interrupted["thread_id"]

        resumed = client.post(
            f"/v1/runs/{interrupted['run_id']}/resume",
            json={"payload": {"age": 31}},
        )
        assert resumed.status_code == 200
        completed = resumed.json()
        assert completed["status"] == "completed"
        assert completed["thread_id"] == interrupted["thread_id"]
        assert completed["answer"] == "user=api-user;age=31"

        events = client.get(f"/v1/runs/{interrupted['run_id']}/events")
        assert events.status_code == 200
        assert "event: run.interrupted" in events.text
        assert "event: run.resumed" in events.text
        assert "event: run.completed" in events.text
