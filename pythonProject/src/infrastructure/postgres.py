"""PostgreSQL lifecycle for durable checkpoints and long-term storage."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.base import BaseStore
from langgraph.store.postgres.aio import AsyncPostgresStore


@dataclass(frozen=True, slots=True)
class PostgresSettings:
    uri: str = field(repr=False)
    pipeline: bool = False

    @classmethod
    def from_env(cls) -> "PostgresSettings":
        uri = os.getenv("POSTGRES_URI", "").strip()
        if not uri:
            raise RuntimeError("POSTGRES_URI is required for the production runtime")
        return cls(
            uri=uri,
            pipeline=os.getenv("PG_PIPELINE", "false").lower() == "true",
        )


@dataclass(frozen=True, slots=True)
class PostgresResources:
    checkpointer: BaseCheckpointSaver
    store: BaseStore


@asynccontextmanager
async def open_postgres_resources(
    settings: PostgresSettings | None = None,
) -> AsyncIterator[PostgresResources]:
    """Open, initialize, and reliably close both PostgreSQL resources."""

    resolved = settings or PostgresSettings.from_env()
    async with AsyncPostgresSaver.from_conn_string(
        resolved.uri,
        pipeline=resolved.pipeline,
    ) as checkpointer:
        await checkpointer.setup()
        async with AsyncPostgresStore.from_conn_string(resolved.uri) as store:
            await store.setup()
            yield PostgresResources(checkpointer=checkpointer, store=store)
