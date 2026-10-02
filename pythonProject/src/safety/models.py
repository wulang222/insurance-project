"""Strict structured contracts for grounded recommendation generation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from harness.result import Citation


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    insurance_type: str = Field(min_length=1)
    min_age: int | None = Field(default=None, ge=0, le=120)
    max_age: int | None = Field(default=None, ge=0, le=120)
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    rationale: str = Field(min_length=1)


class FactualClaim(BaseModel):
    """A claim must name exactly one auditable source boundary."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_type: Literal["product_field", "citation", "business_rule"]
    product_id: str | None = None
    field_name: str | None = None
    value: Any | None = None
    citation_id: str | None = None
    rule_version: str | None = None

    @model_validator(mode="after")
    def require_source_reference(self) -> "FactualClaim":
        required = {
            "product_field": bool(self.product_id and self.field_name),
            "citation": bool(self.citation_id),
            "business_rule": bool(self.rule_version),
        }
        if not required[self.source_type]:
            raise ValueError(f"{self.source_type} claim is missing its source reference")
        return self


class RecommendationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    recommendations: list[Recommendation] = Field(default_factory=list)
    factual_claims: list[FactualClaim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)


class ComplianceViolation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    claim_id: str | None = None
    product_id: str | None = None
    level: Literal["code", "evaluator"]


class ComplianceDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    violations: list[ComplianceViolation] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
    revision_count: int = Field(default=0, ge=0, le=1)
    code_checks_passed: bool = False
    evaluator_passed: bool = False
