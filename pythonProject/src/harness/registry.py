"""Immutable specialist definitions and per-call allowlist enforcement."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agents.schemas import (
    CRMAgentInput,
    CRMAgentOutput,
    ComplianceAgentInput,
    ComplianceAgentOutput,
    CoverageGapAgentInput,
    CoverageGapAgentOutput,
    KnowledgeAgentInput,
    KnowledgeAgentOutput,
    ProductAgentInput,
    ProductAgentOutput,
    ProfileAgentInput,
    ProfileAgentOutput,
)
from harness.errors import PolicyDeniedError
from tools.base import ToolCallContext


class AgentSpec(BaseModel):
    """Singleton definition. Runtime state is deliberately not stored here."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    allowed_tools: list[str] = Field(default_factory=list)
    prompt_id: str = Field(min_length=1)
    max_model_calls: int = Field(ge=0)


class AgentRegistry:
    def __init__(
        self,
        specs: tuple[AgentSpec, ...],
        *,
        known_tools: set[str] | None = None,
    ) -> None:
        definitions: dict[str, AgentSpec] = {}
        for spec in specs:
            if spec.name in definitions:
                raise ValueError(f"duplicate agent definition: {spec.name}")
            if known_tools is not None:
                unknown = set(spec.allowed_tools) - known_tools
                if unknown:
                    raise ValueError(
                        f"agent {spec.name} references unknown tools: {sorted(unknown)}"
                    )
            definitions[spec.name] = spec
        self._definitions = definitions

    def get(self, name: str) -> AgentSpec:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise KeyError(f"unknown agent: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(self._definitions)

    def validate_input(self, agent_name: str, value: Any) -> BaseModel:
        return self.get(agent_name).input_schema.model_validate(value)

    def validate_output(self, agent_name: str, value: Any) -> BaseModel:
        return self.get(agent_name).output_schema.model_validate(value)

    async def execute_tool(
        self,
        agent_name: str,
        tool_gateway: Any,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        context: ToolCallContext,
    ) -> Any:
        spec = self.get(agent_name)
        if tool_name not in spec.allowed_tools:
            raise PolicyDeniedError(
                f"agent {agent_name} is not allowed to use {tool_name}",
                details={"agent": agent_name, "tool": tool_name},
            )
        return await tool_gateway.execute(tool_name, arguments, context=context)


AGENT_SPECS: tuple[AgentSpec, ...] = (
    AgentSpec(
        name="profile_agent",
        version="1.0.0",
        description="Extract and validate the household insurance profile.",
        capabilities=["profile.extract", "profile.validate", "memory.write"],
        input_schema=ProfileAgentInput,
        output_schema=ProfileAgentOutput,
        allowed_tools=[
            "extract_customer_profile",
            "get_profile_memory",
            "save_profile_memory",
        ],
        prompt_id="recommendation.profile_extract",
        max_model_calls=2,
    ),
    AgentSpec(
        name="crm_agent",
        version="1.0.0",
        description="Read the customer's current policy portfolio.",
        capabilities=["crm.read", "portfolio.read"],
        input_schema=CRMAgentInput,
        output_schema=CRMAgentOutput,
        allowed_tools=["get_customer_policy_portfolio"],
        prompt_id="crm.portfolio",
        max_model_calls=0,
    ),
    AgentSpec(
        name="coverage_gap_agent",
        version="1.0.0",
        description="Calculate configured demonstration coverage gaps.",
        capabilities=["coverage.calculate"],
        input_schema=CoverageGapAgentInput,
        output_schema=CoverageGapAgentOutput,
        allowed_tools=["calculate_coverage_gap"],
        prompt_id="coverage.rules",
        max_model_calls=0,
    ),
    AgentSpec(
        name="product_agent",
        version="1.0.0",
        description="Find active products matching the highest-priority gaps.",
        capabilities=["product.search", "product.eligibility"],
        input_schema=ProductAgentInput,
        output_schema=ProductAgentOutput,
        allowed_tools=["search_active_insurance_products", "get_product_eligibility"],
        prompt_id="recommendation.generate",
        max_model_calls=1,
    ),
    AgentSpec(
        name="knowledge_agent",
        version="1.0.0",
        description="Retrieve policy evidence for the identified gaps.",
        capabilities=["policy.retrieve", "knowledge.explain"],
        input_schema=KnowledgeAgentInput,
        output_schema=KnowledgeAgentOutput,
        allowed_tools=["retrieve_policy_evidence"],
        prompt_id="knowledge.answer",
        max_model_calls=1,
    ),
    AgentSpec(
        name="compliance_agent",
        version="1.0.0",
        description="Check product facts, evidence boundaries, and wording.",
        capabilities=["compliance.check", "facts.check"],
        input_schema=ComplianceAgentInput,
        output_schema=ComplianceAgentOutput,
        allowed_tools=[],
        prompt_id="family.compliance",
        max_model_calls=1,
    ),
)


def build_agent_registry(known_tools: set[str] | None = None) -> AgentRegistry:
    return AgentRegistry(AGENT_SPECS, known_tools=known_tools)


agent_registry = build_agent_registry()
