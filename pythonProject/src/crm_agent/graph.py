"""
CRM Agent — LangGraph 工作流

客户关系管理智能分析：
  1. 加载客户数据（画像 + 保单 + 交互记录）
  2. LLM 情感分析
  3. 流失风险预测（规则 + LLM 双引擎）
  4. 加购机会识别
  5. 生成 CRM 综合报告

简化设计：线性流程，无复杂分支，便于维护和演示
"""

from __future__ import annotations

import json
import logging

from langgraph.graph import StateGraph, END

from crm_agent.state import CRMAgentState
from crm_agent.config import create_llm
from crm_agent.prompts import CRM_REPORT_PROMPT
from crm_agent.tools import (
    load_customer_data,
    analyze_sentiment,
    predict_churn_risk,
    identify_upsell_opportunities,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Node 1: 加载客户数据
# ═══════════════════════════════════════════════════════════════

async def load_customer_node(state: CRMAgentState) -> dict:
    """从数据源加载客户的完整CRM数据"""
    user_id = state.get("user_id", "")
    messages = state.get("messages", [])

    # 当请求携带消息但未指定用户时，保留原有默认用户行为。
    if not user_id and messages:
        user_id = "default_user"

    data = load_customer_data.invoke({"user_id": user_id})

    return {
        "user_id": user_id,
        "customer_profile": data.get("profile", {}),
        "policies": data.get("policies", []),
        "interaction_history": data.get("interactions", []),
    }


# ═══════════════════════════════════════════════════════════════
# Node 2: 情感分析
# ═══════════════════════════════════════════════════════════════

async def sentiment_node(state: CRMAgentState) -> dict:
    """LLM 分析客户交互记录中的情感和决策信号"""
    interactions = state.get("interaction_history", [])
    if not interactions:
        return {"sentiment_summary": "无交互记录"}

    result = analyze_sentiment.invoke({
        "interactions_json": json.dumps(interactions, ensure_ascii=False)
    })

    return {"sentiment_summary": json.dumps(result, ensure_ascii=False)}


# ═══════════════════════════════════════════════════════════════
# Node 3: 流失风险预测
# ═══════════════════════════════════════════════════════════════

async def churn_node(state: CRMAgentState) -> dict:
    """规则引擎 + LLM 双重预测流失风险"""
    policies = state.get("policies", [])
    sentiment = state.get("sentiment_summary", "{}")
    profile = state.get("customer_profile", {})

    result = predict_churn_risk.invoke({
        "policies_json": json.dumps(policies, ensure_ascii=False),
        "sentiment_json": sentiment,
        "profile_json": json.dumps(profile, ensure_ascii=False),
    })

    return {
        "churn_risk": result.get("churn_risk", 0),
        "churn_reason": json.dumps(result.get("risk_factors", []), ensure_ascii=False),
        "key_time_nodes": result.get("key_time_nodes", []),
    }


# ═══════════════════════════════════════════════════════════════
# Node 4: 加购机会识别
# ═══════════════════════════════════════════════════════════════

async def upsell_node(state: CRMAgentState) -> dict:
    """分析保单缺口，识别加购/升级机会"""
    profile = state.get("customer_profile", {})
    policies = state.get("policies", [])

    opportunities = identify_upsell_opportunities.invoke({
        "profile_json": json.dumps(profile, ensure_ascii=False),
        "policies_json": json.dumps(policies, ensure_ascii=False),
    })

    return {"upsell_opportunities": opportunities}


# ═══════════════════════════════════════════════════════════════
# Node 5: 生成 CRM 综合报告
# ═══════════════════════════════════════════════════════════════

async def generate_report_node(state: CRMAgentState) -> dict:
    """LLM 综合所有分析结果，生成面向销售团队的CRM报告"""
    try:
        import json as json_mod

        churn_reason = state.get("churn_reason", "[]")
        if isinstance(churn_reason, str):
            try:
                risk_factors = json_mod.loads(churn_reason)
            except (json_mod.JSONDecodeError, TypeError):
                risk_factors = [churn_reason]
        else:
            risk_factors = churn_reason

        risk_level = (
            "high" if state.get("churn_risk", 0) >= 60
            else "medium" if state.get("churn_risk", 0) >= 30
            else "low"
        )

        prompt = CRM_REPORT_PROMPT.format(
            profile=json.dumps(state.get("customer_profile", {}), ensure_ascii=False, indent=2),
            policies=json.dumps(state.get("policies", []), ensure_ascii=False, indent=2),
            sentiment=state.get("sentiment_summary", "无数据"),
            churn_risk=state.get("churn_risk", 0),
            risk_level=risk_level,
            risk_factors=json.dumps(risk_factors, ensure_ascii=False),
            key_nodes=json.dumps(state.get("key_time_nodes", []), ensure_ascii=False, indent=2),
            upsell=json.dumps(state.get("upsell_opportunities", []), ensure_ascii=False, indent=2),
        )

        llm = create_llm(temperature=0.4)
        response = llm.invoke(prompt)
        report = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.warning(f"生成CRM报告失败: {e}，使用简单模板")
        report = _simple_report(state)

    return {"crm_report": report}


def _simple_report(state: CRMAgentState) -> str:
    """LLM不可用时的简单报告模板"""
    profile = state.get("customer_profile", {})
    churn = state.get("churn_risk", 0)
    upsells = state.get("upsell_opportunities", [])
    nodes = state.get("key_time_nodes", [])

    risk_emoji = "🔴" if churn >= 60 else "🟡" if churn >= 30 else "🟢"

    lines = [
        "## 📊 CRM 客户洞察报告",
        "",
        "### 客户概览",
        f"- 客户: {profile.get('name', '未知')}",
        f"- 等级: {profile.get('membership_level', 'standard')}",
        f"- 年度保费: {profile.get('total_premium', 0)}元",
        "",
        "### ⚠️ 风险预警",
        f"{risk_emoji} 流失风险评分: {churn}/100",
    ]

    if nodes:
        for n in nodes[:5]:
            lines.append(f"- {n.get('type','')}: {n.get('policy_name','')} ({n.get('days_left','')}天后)")

    if upsells:
        lines.append("")
        lines.append("### 💡 加购建议")
        for u in upsells[:3]:
            lines.append(f"- [{u.get('priority','')}] {u.get('product_type','')}: {u.get('reason','')}")

    lines.append("")
    lines.append("### 📋 建议行动")
    lines.append(f"1. 优先处理保单续保提醒（共{len(nodes)}个关键节点）")
    lines.append("2. 跟进客户情感趋势，主动联系了解需求")
    lines.append(f"3. 推荐{len(upsells)}个加购机会，优先高优先级产品")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Build the Graph
# ═══════════════════════════════════════════════════════════════

def build_graph(*, checkpointer=None, store=None):
    """构建 CRM Agent 工作流

    Returns:
        编译后的 StateGraph
    """
    workflow = StateGraph(CRMAgentState)

    # 添加节点
    workflow.add_node("load_customer", load_customer_node)
    workflow.add_node("analyze_sentiment", sentiment_node)
    workflow.add_node("predict_churn", churn_node)
    workflow.add_node("identify_upsell", upsell_node)
    workflow.add_node("generate_report", generate_report_node)

    # 线性流程
    workflow.set_entry_point("load_customer")
    workflow.add_edge("load_customer", "analyze_sentiment")
    workflow.add_edge("analyze_sentiment", "predict_churn")
    workflow.add_edge("predict_churn", "identify_upsell")
    workflow.add_edge("identify_upsell", "generate_report")
    workflow.add_edge("generate_report", END)

    return workflow.compile(checkpointer=checkpointer, store=store)


# 模块级 graph 实例
graph = build_graph()
