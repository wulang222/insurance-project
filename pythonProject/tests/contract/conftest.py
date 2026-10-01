"""Isolation fixtures for baseline contract tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


class FakeLLM:
    """Deterministic replacement for provider-backed routing calls."""

    def invoke(self, prompt: object) -> SimpleNamespace:
        return SimpleNamespace(
            content='{"route":"knowledge_agent","reason":"contract-test stub"}'
        )


@pytest.fixture
def mocked_external_services(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    """Prevent contract tests from reaching LLM, MySQL, or Milvus."""

    import pymysql
    import insurance_agent.tools as insurance_tools
    import shared.milvus_utils as milvus_utils
    import supervisor_agent.graph as supervisor_graph

    fake_llm = FakeLLM()
    monkeypatch.setattr(supervisor_graph, "create_llm", lambda **_: fake_llm)
    monkeypatch.setattr(
        pymysql,
        "connect",
        lambda **_: (_ for _ in ()).throw(
            AssertionError("contract tests must not connect to MySQL")
        ),
    )
    monkeypatch.setattr(milvus_utils, "is_milvus_available", lambda: False)
    monkeypatch.setattr(milvus_utils, "milvus_search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(insurance_tools, "is_milvus_available", lambda: False)
    monkeypatch.setattr(
        insurance_tools,
        "milvus_search",
        lambda *_args, **_kwargs: [],
    )
    return fake_llm
