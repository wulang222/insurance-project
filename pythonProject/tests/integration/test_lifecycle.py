from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

import server
from harness.lifecycle import build_lifespan
from infrastructure.postgres import PostgresResources


class CloseTrackedClient:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class FakeGraph:
    async def ainvoke(self, input_data, config):
        return {"final_answer": "ok", "handled_by": "knowledge_agent"}


def test_fastapi_lifespan_creates_and_releases_resources() -> None:
    mysql_client = CloseTrackedClient()
    milvus_client = CloseTrackedClient()
    resources = PostgresResources(
        checkpointer=MemorySaver(),
        store=InMemoryStore(),
    )

    @asynccontextmanager
    async def postgres_factory():
        yield resources

    lifespan = build_lifespan(
        postgres_factory=postgres_factory,
        mysql_factory=lambda: mysql_client,
        milvus_factory=lambda: milvus_client,
        graph_factory=lambda **_: FakeGraph(),
    )
    app = server.create_app(lifespan=lifespan)

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.json()["runtime"] == "ready"
        assert app.state.dependencies.checkpointer is resources.checkpointer
        assert app.state.dependencies.store is resources.store
        assert app.state.dependencies.prompt_registry is not None
        assert app.state.dependencies.model_gateway is not None
        assert app.state.dependencies.tool_gateway is not None
        assert app.state.dependencies.agent_registry is not None

    assert mysql_client.closed is True
    assert milvus_client.closed is True
    assert app.state.runtime is None
    assert app.state.dependencies is None
