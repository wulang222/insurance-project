"""FastAPI lifespan that owns every runtime dependency."""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI

from harness.dependencies import AgentDependencies
from harness.registry import build_agent_registry
from harness.runtime import RunManager
from infrastructure.milvus import MilvusClient
from infrastructure.mysql import MySQLClient
from infrastructure.postgres import PostgresResources, open_postgres_resources
from insurance_agent.config import create_llm
from middleware.model import ModelGateway
from middleware.tool import ToolGateway
from observability.telemetry import Observability
from prompts.registry import PromptRegistry
from supervisor_agent.graph import build_graph as build_supervisor_graph
from tools.crm_tools import FakeCustomerRepository
from tools.memory_tools import ProfileMemoryRepository
from tools.policy_tools import MilvusPolicyEvidenceRepository
from tools.product_tools import MySQLProductRepository
from tools.registry import build_tool_registry


PostgresFactory = Callable[[], AbstractAsyncContextManager[PostgresResources]]


def build_lifespan(
    *,
    postgres_factory: PostgresFactory = open_postgres_resources,
    mysql_factory: Callable[[], Any] = MySQLClient.from_env,
    milvus_factory: Callable[[], Any] = MilvusClient.from_env,
    graph_factory: Callable[..., Any] = build_supervisor_graph,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Create an injectable lifespan; production defaults always use PostgreSQL."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with postgres_factory() as postgres:
            mysql_client = mysql_factory()
            milvus_client = milvus_factory()
            prompt_registry = PromptRegistry.default()
            observability = Observability()
            model_gateway = ModelGateway(
                create_llm,
                prompt_registry,
                observability=observability,
            )
            tool_registry = build_tool_registry(
                model_gateway=model_gateway,
                product_repository=MySQLProductRepository(mysql_client),
                evidence_repository=MilvusPolicyEvidenceRepository(milvus_client),
                customer_repository=FakeCustomerRepository(),
                memory_repository=ProfileMemoryRepository(postgres.store),
            )
            tool_gateway = ToolGateway(tool_registry, observability=observability)
            specialist_registry = build_agent_registry(set(tool_registry.names()))
            dependencies = AgentDependencies(
                llm_factory=create_llm,
                checkpointer=postgres.checkpointer,
                store=postgres.store,
                tool_gateway=tool_gateway,
                model_gateway=model_gateway,
                prompt_registry=prompt_registry,
                agent_registry=specialist_registry,
                tracer=observability,
                mysql_client=mysql_client,
                milvus_client=milvus_client,
            )
            graph = graph_factory(
                checkpointer=postgres.checkpointer,
                store=postgres.store,
                dependencies=dependencies,
            )
            runtime = RunManager(
                graph,
                postgres.store,
                prompt_version=os.getenv("AGENT_PROMPT_VERSION", "v1"),
                model_policy=os.getenv("AGENT_MODEL_POLICY", "balanced"),
                observability=observability,
            )

            app.state.dependencies = dependencies
            app.state.runtime = runtime
            app.state.observability = observability
            try:
                yield
            finally:
                await milvus_client.aclose()
                await mysql_client.aclose()
                app.state.runtime = None
                app.state.dependencies = None
                app.state.observability = None

    return lifespan


production_lifespan = build_lifespan()
