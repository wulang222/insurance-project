from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness.errors import PolicyDeniedError
from harness.registry import AGENT_SPECS, build_agent_registry
from prompts.registry import PromptRegistry
from tools.base import ToolCallContext


EXPECTED_AGENTS = {
    "profile_agent",
    "crm_agent",
    "coverage_gap_agent",
    "product_agent",
    "knowledge_agent",
    "compliance_agent",
}


def test_registry_contains_all_required_specialists() -> None:
    registry = build_agent_registry()
    assert set(registry.names()) == EXPECTED_AGENTS
    for name in EXPECTED_AGENTS:
        spec = registry.get(name)
        assert spec.version
        assert spec.capabilities
        assert spec.input_schema is not None
        assert spec.output_schema is not None


def test_agent_specs_are_immutable_singleton_definitions() -> None:
    spec = AGENT_SPECS[0]
    with pytest.raises(ValidationError):
        spec.name = "changed"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_agent_tool_allowlist_denies_before_gateway() -> None:
    class Gateway:
        called = False

        async def execute(self, *args, **kwargs):
            self.called = True

    gateway = Gateway()
    registry = build_agent_registry()
    with pytest.raises(PolicyDeniedError):
        await registry.execute_tool(
            "compliance_agent",
            gateway,
            "save_profile_memory",
            {},
            context=ToolCallContext(request_id="request", run_id="run"),
        )
    assert gateway.called is False


def test_registry_rejects_unknown_tool_references() -> None:
    with pytest.raises(ValueError, match="unknown tools"):
        build_agent_registry(known_tools={"retrieve_policy_evidence"})


def test_every_agent_prompt_id_is_versioned_in_prompt_registry() -> None:
    prompts = PromptRegistry.default()
    for spec in AGENT_SPECS:
        assert prompts.get(spec.prompt_id, "v1").version == "v1"
