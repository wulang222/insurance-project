"""In-memory registry for explicit, versioned tool definitions."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from middleware.model import ModelCallContext, ModelGateway, ModelRequest
from tools.base import ToolCallContext, ToolSpec
from tools.crm_tools import (
    CustomerPortfolio,
    CustomerPortfolioInput,
    CustomerRepository,
)
from tools.memory_tools import (
    LoadProfileInput,
    LoadProfileResult,
    ProfileMemoryRepository,
    SaveProfileInput,
    SaveProfileResult,
)
from tools.policy_tools import (
    CoverageGapInput,
    CoverageGapResult,
    EligibilityInput,
    EligibilityResult,
    Evidence,
    EvidenceInput,
    PolicyEvidenceRepository,
    calculate_coverage_gap,
    get_product_eligibility,
)
from tools.product_tools import Product, ProductRepository, ProductSearchInput
from tools.base import ToolDefinition


class ToolRegistry:
    def __init__(self, definitions: list[ToolDefinition] | None = None) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        for definition in definitions or []:
            self.register(definition)

    def register(self, definition: ToolDefinition) -> None:
        name = definition.spec.name
        if name in self._definitions:
            raise ValueError(f"duplicate tool definition: {name}")
        self._definitions[name] = definition

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))


class CustomerProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation: str = Field(min_length=1)
    stored_profile_json: str = "{}"


class CustomerProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: int | None = Field(default=None, ge=0, le=120)
    occupation: str | None = None
    budget: float | None = Field(default=None, ge=0)
    insurance_type: str | None = None


def build_tool_registry(
    *,
    model_gateway: ModelGateway,
    product_repository: ProductRepository,
    evidence_repository: PolicyEvidenceRepository,
    customer_repository: CustomerRepository,
    memory_repository: ProfileMemoryRepository,
) -> ToolRegistry:
    """Build the first governed business-tool catalog required by Day 3."""

    async def extract_customer_profile(
        conversation: str,
        stored_profile_json: str,
        context: ToolCallContext,
    ) -> CustomerProfile:
        try:
            result = await model_gateway.invoke(
                ModelRequest(
                    prompt_id="recommendation.profile_extract",
                    variables={
                        "conversation": conversation,
                        "stored_profile_json": stored_profile_json,
                    },
                    strategy="extract",
                    response_model=CustomerProfile,
                ),
                context=ModelCallContext(
                    request_id=context.request_id,
                    run_id=context.run_id,
                    user_id=context.user_id,
                    max_model_calls=context.max_model_calls,
                    model_policy=context.model_policy,
                    prompt_versions=context.prompt_versions,
                ),
            )
            return result.data
        except Exception:
            # Deterministic extraction is a safe degradation path, not fake business data.
            return _regex_profile(conversation)

    async def search_active_insurance_products(**kwargs: Any) -> list[dict[str, Any]]:
        query = ProductSearchInput.model_validate(kwargs)
        return await asyncio.to_thread(product_repository.search_active, query)

    async def retrieve_policy_evidence(
        query: str,
        product_ids: list[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            evidence_repository.search,
            query,
            product_ids=product_ids,
            top_k=top_k,
        )

    async def get_customer_policy_portfolio(user_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(customer_repository.get_portfolio, user_id)

    async def save_profile_memory(
        user_id: str,
        profile: dict[str, Any],
        interaction: dict[str, Any] | None,
    ) -> SaveProfileResult:
        return await memory_repository.save(user_id, profile, interaction)

    async def get_profile_memory(user_id: str) -> LoadProfileResult:
        return await memory_repository.load(user_id)

    return ToolRegistry(
        [
            ToolDefinition(
                ToolSpec(
                    name="extract_customer_profile",
                    version="1.0.0",
                    description="Extract a validated insurance customer profile.",
                    risk_level="read",
                    idempotent=True,
                    timeout_seconds=35,
                    required_scopes=["insurance:read"],
                ),
                CustomerProfileInput,
                CustomerProfile,
                extract_customer_profile,
            ),
            ToolDefinition(
                ToolSpec(
                    name="search_active_insurance_products",
                    version="1.0.0",
                    description="Search only active insurance products.",
                    risk_level="read",
                    idempotent=True,
                    timeout_seconds=8,
                    required_scopes=["insurance:read"],
                ),
                ProductSearchInput,
                list[Product],
                search_active_insurance_products,
            ),
            ToolDefinition(
                ToolSpec(
                    name="get_product_eligibility",
                    version="1.0.0",
                    description="Evaluate product age, occupation and budget constraints.",
                    risk_level="read",
                    idempotent=True,
                    timeout_seconds=2,
                    required_scopes=["insurance:read"],
                ),
                EligibilityInput,
                EligibilityResult,
                get_product_eligibility,
            ),
            ToolDefinition(
                ToolSpec(
                    name="retrieve_policy_evidence",
                    version="1.0.0",
                    description="Retrieve policy and product evidence from the knowledge base.",
                    risk_level="read",
                    idempotent=True,
                    timeout_seconds=10,
                    required_scopes=["knowledge:read"],
                ),
                EvidenceInput,
                list[Evidence],
                retrieve_policy_evidence,
            ),
            ToolDefinition(
                ToolSpec(
                    name="get_customer_policy_portfolio",
                    version="1.0.0",
                    description="Load a customer's policy portfolio from the configured CRM repository.",
                    risk_level="read",
                    idempotent=True,
                    timeout_seconds=5,
                    required_scopes=["crm:read"],
                ),
                CustomerPortfolioInput,
                CustomerPortfolio,
                get_customer_policy_portfolio,
            ),
            ToolDefinition(
                ToolSpec(
                    name="calculate_coverage_gap",
                    version="1.0.0",
                    description="Calculate missing protection categories from a portfolio.",
                    risk_level="read",
                    idempotent=True,
                    timeout_seconds=2,
                    required_scopes=["crm:read"],
                ),
                CoverageGapInput,
                CoverageGapResult,
                calculate_coverage_gap,
            ),
            ToolDefinition(
                ToolSpec(
                    name="get_profile_memory",
                    version="1.0.0",
                    description="Read the current persisted customer profile.",
                    risk_level="read",
                    idempotent=True,
                    timeout_seconds=5,
                    required_scopes=["memory:read"],
                ),
                LoadProfileInput,
                LoadProfileResult,
                get_profile_memory,
            ),
            ToolDefinition(
                ToolSpec(
                    name="save_profile_memory",
                    version="1.0.0",
                    description="Persist a customer profile and optional interaction summary.",
                    risk_level="write",
                    idempotent=False,
                    timeout_seconds=5,
                    required_scopes=["memory:write"],
                ),
                SaveProfileInput,
                SaveProfileResult,
                save_profile_memory,
            ),
        ]
    )


def _regex_profile(conversation: str) -> CustomerProfile:
    age_match = re.search(r"(\d{1,3})\s*岁", conversation)
    budget_match = re.search(r"(?:预算|保费|每年).*?(\d{2,7})", conversation)
    occupations = ("程序员", "教师", "医生", "护士", "律师", "工程师", "设计师", "销售", "会计", "公务员")
    insurance_types = ("重疾险", "医疗险", "意外险", "寿险", "年金险")
    return CustomerProfile(
        age=int(age_match.group(1)) if age_match else None,
        occupation=next((item for item in occupations if item in conversation), None),
        budget=float(budget_match.group(1)) if budget_match else None,
        insurance_type=next((item for item in insurance_types if item in conversation), None),
    )
