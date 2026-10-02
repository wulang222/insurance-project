"""Typed inputs and outputs for the Day 4 specialist agents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from tools.policy_tools import Evidence
from tools.product_tools import Product


class FamilyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: int = Field(ge=0, le=120)
    occupation: str | None = None
    budget: float | None = Field(default=None, ge=0)
    insurance_type: str | None = None


class CoverageGap(BaseModel):
    """Rule-derived demo gap; never represents underwriting advice."""

    model_config = ConfigDict(extra="forbid")

    category: Literal["critical_illness", "medical", "accident", "life"]
    current_coverage: float = Field(ge=0)
    recommended_coverage: float = Field(ge=0)
    gap: float = Field(ge=0)
    priority: Literal["high", "medium", "low"]
    rationale: str = Field(min_length=1)


class ProfileAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation: str
    stored_profile_json: str = "{}"


class ProfileAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: FamilyProfile


class CRMAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str


class CRMAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    portfolio: list[dict[str, Any]] = Field(default_factory=list)
    crm_available: bool = True
    warnings: list[str] = Field(default_factory=list)


class CoverageGapAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: FamilyProfile
    portfolio: list[dict[str, Any]] = Field(default_factory=list)


class CoverageGapAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coverage_gaps: list[CoverageGap]
    disclaimer: str


class ProductAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: FamilyProfile
    coverage_gaps: list[CoverageGap]


class ProductAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    products: list[Product] = Field(default_factory=list)


class KnowledgeAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coverage_gaps: list[CoverageGap]


class KnowledgeAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AggregateAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: FamilyProfile
    portfolio: list[dict[str, Any]]
    coverage_gaps: list[CoverageGap]
    products: list[Product]
    evidence: list[Evidence]
    warnings: list[str] = Field(default_factory=list)


class AggregateAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: str = Field(min_length=1)


class ComplianceAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: str
    products: list[Product]
    evidence: list[Evidence]
    warnings: list[str] = Field(default_factory=list)


class ComplianceAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    final_answer: str = Field(min_length=1)
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
