"""State definitions for the insurance recommendation agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


# 用户画像
@dataclass
class UserProfile:
    """Extracted and validated user profile for insurance matching."""
    age: int | None = None
    occupation: str | None = None
    budget: float | None = None
    insurance_type: str | None = None


# 保险产品
@dataclass
class InsuranceProduct:
    """An insurance product returned by MySQL strict matching."""
    product_id: str
    product_name: str
    insurance_type: str
    min_age: int
    max_age: int
    min_price: float
    max_price: float
    target_occupations: str
    description: str


# Sentinel for interrupt-carrying field
MISSING = "__MISSING__"


# Required fields and their Chinese descriptions
REQUIRED_FIELDS: dict[str, str] = {
    "age": "年龄",
    "occupation": "职业",
    "budget": "预算",
    "insurance_type": "保险类型",
}


# 保险推荐 agent 的 State（TypedDict，LangGraph 原生支持）
class InsuranceAgentState(TypedDict, total=False):
    """Typed state for the insurance recommendation agent graph.

    Keys used by the workflow:
    - messages: list           — conversation history（Annotated + add_messages 累加）
    - user_id: str             — 用户标识（用于跨会话 Store 读写）
    - user_profile_raw: dict   — raw LLM-extracted profile
    - user_profile: UserProfile|None — validated profile
    - matched_products: list[dict]   — MySQL strict-matched products
    - enriched_products: list[dict]  — products with RAG context
    - final_recommendation: str      — final recommendation text
    - interrupt_reason: str          — reason for human-in-the-loop interrupt
    - profile_source: str            — 画像来源
    - stored_profile: dict           — Store历史画像
    """
    messages: Annotated[list, add_messages]
    user_id: str
    user_profile_raw: dict
    user_profile: UserProfile | None
    matched_products: list[dict]
    enriched_products: list[dict]
    final_recommendation: str
    interrupt_reason: str
    profile_source: str
    stored_profile: dict
