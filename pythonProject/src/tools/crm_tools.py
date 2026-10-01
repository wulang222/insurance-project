"""Customer portfolio repository contract and explicit fake adapter."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class CustomerPortfolioInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1)


class CustomerPortfolio(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    policies: list[dict[str, Any]] = Field(default_factory=list)
    interactions: list[dict[str, Any]] = Field(default_factory=list)


class CustomerRepository(Protocol):
    def get_portfolio(self, user_id: str) -> dict[str, Any]: ...


class FakeCustomerRepository:
    """Explicit adapter used until a real CRM repository is configured."""

    def __init__(self, customers: dict[str, dict[str, Any]] | None = None) -> None:
        self.customers = customers or {}

    def get_portfolio(self, user_id: str) -> dict[str, Any]:
        return self.customers.get(
            user_id,
            {"profile": {"user_id": user_id}, "policies": [], "interactions": []},
        )
