"""
CRM Agent — 状态定义（TypedDict，LangGraph 原生支持）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


@dataclass
class CustomerPolicy:
    """客户持有的保单"""
    policy_id: str
    product_name: str
    insurance_type: str
    premium: float
    insured_amount: float
    start_date: str
    end_date: str
    status: str  # active / expiring_soon / expired / claimed
    renewal_reminder_sent: bool = False


@dataclass
class CustomerInteraction:
    """客户交互记录"""
    interaction_id: str
    interaction_type: str  # chat / phone / email / meeting
    timestamp: str
    summary: str
    sentiment_label: str  # positive / neutral / negative
    key_topics: list[str] = field(default_factory=list)


@dataclass
class CustomerProfile:
    """客户画像（CRM维度）"""
    user_id: str
    name: str
    age: int | None = None
    occupation: str | None = None
    membership_level: str = "standard"
    total_premium: float = 0.0
    customer_since: str = ""


class CRMAgentState(TypedDict, total=False):
    """CRM Agent 状态容器

    各字段说明:
    - messages:               对话历史
    - user_id:                用户标识
    - customer_profile:       客户画像 (dict)
    - policies:               保单列表 list[dict]
    - interaction_history:    交互记录 list[dict]
    - sentiment_summary:      LLM情感分析摘要
    - churn_risk:             流失风险 (0-100)
    - churn_reason:           流失原因分析
    - key_time_nodes:         关键时间节点列表
    - upsell_opportunities:   加购机会列表
    - crm_report:             最终CRM综合报告
    """
    messages: Annotated[list, add_messages]
    user_id: str
    customer_profile: dict | None
    policies: list[dict]
    interaction_history: list[dict]
    sentiment_summary: str
    churn_risk: int
    churn_reason: str
    key_time_nodes: list[dict]
    upsell_opportunities: list[dict]
    crm_report: str
