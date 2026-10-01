"""
CRM Agent — 工具函数

提供客户数据加载、情感分析、流失预测、加购识别等工具
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from langchain_core.tools import tool

from crm_agent.config import create_llm

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Tool 1: 加载客户数据
# ═══════════════════════════════════════════════════════════════

@tool
def load_customer_data(user_id: str) -> dict:
    """加载客户的完整CRM数据：画像、保单、交互历史。

    Args:
        user_id: 用户ID

    Returns:
        dict with keys: profile, policies, interactions
    """
    # 后续接入真实数据库，当前使用Mock数据
    return _mock_customer_data(user_id)


def _mock_customer_data(user_id: str) -> dict:
    """Mock 客户数据（演示用）"""
    now = datetime.now()
    fmt = "%Y-%m-%d"

    profile = {
        "user_id": user_id,
        "name": "张先生",
        "age": 35,
        "occupation": "软件工程师",
        "membership_level": "gold",
        "total_premium": 12800.0,
        "customer_since": "2022-03-15",
    }

    # 保单：关注续保/即将到期
    policies = [
        {
            "policy_id": f"POL-{user_id}-001",
            "product_name": "安心保·重疾险（标准版）",
            "insurance_type": "重疾险",
            "premium": 4500.0,
            "insured_amount": 500000.0,
            "start_date": "2025-01-01",
            "end_date": "2026-01-01",
            "status": "active",
            "renewal_reminder_sent": False,
        },
        {
            "policy_id": f"POL-{user_id}-002",
            "product_name": "全民e保·百万医疗险",
            "insurance_type": "医疗险",
            "premium": 680.0,
            "insured_amount": 4000000.0,
            "start_date": "2025-06-01",
            "end_date": "2026-06-01",
            "status": "expiring_soon",  # 即将到期！
            "renewal_reminder_sent": False,
        },
        {
            "policy_id": f"POL-{user_id}-003",
            "product_name": "平安行·综合意外险",
            "insurance_type": "意外险",
            "premium": 360.0,
            "insured_amount": 800000.0,
            "start_date": "2025-03-01",
            "end_date": "2026-03-01",
            "status": "expired",  # 已过期！
            "renewal_reminder_sent": False,
        },
    ]

    # 交互历史
    interactions = [
        {
            "interaction_id": f"INT-{user_id}-001",
            "interaction_type": "chat",
            "timestamp": (now - timedelta(days=2)).strftime(fmt),
            "summary": "客户咨询重疾险理赔流程，对理赔速度表示担忧",
            "sentiment_label": "neutral",
            "key_topics": ["理赔流程", "理赔速度"],
        },
        {
            "interaction_id": f"INT-{user_id}-002",
            "interaction_type": "chat",
            "timestamp": (now - timedelta(days=7)).strftime(fmt),
            "summary": "客户询问医疗险续保是否有优惠，提到对比了其他公司的产品",
            "sentiment_label": "neutral",
            "key_topics": ["续保优惠", "竞品对比"],
        },
        {
            "interaction_id": f"INT-{user_id}-003",
            "interaction_type": "phone",
            "timestamp": (now - timedelta(days=30)).strftime(fmt),
            "summary": "客服回访，客户对产品总体满意但希望增加家庭成员保障",
            "sentiment_label": "positive",
            "key_topics": ["满意度", "家庭保障"],
        },
        {
            "interaction_id": f"INT-{user_id}-004",
            "interaction_type": "chat",
            "timestamp": (now - timedelta(days=60)).strftime(fmt),
            "summary": "客户抱怨意外险保费涨价，表达不满",
            "sentiment_label": "negative",
            "key_topics": ["保费涨价", "不满"],
        },
    ]

    return {
        "profile": profile,
        "policies": policies,
        "interactions": interactions,
    }


# ═══════════════════════════════════════════════════════════════
# Tool 2: LLM 情感分析
# ═══════════════════════════════════════════════════════════════

@tool
def analyze_sentiment(interactions_json: str) -> dict:
    """使用LLM分析客户交互记录中的情感趋势和决策倾向。

    Args:
        interactions_json: JSON字符串，交互记录列表

    Returns:
        dict with keys: overall_sentiment, sentiment_trend, decision_signals, risk_flags
    """
    from crm_agent.prompts import SENTIMENT_ANALYSIS_PROMPT

    interactions = json.loads(interactions_json) if isinstance(interactions_json, str) else interactions_json
    if not interactions:
        return {
            "overall_sentiment": "无数据",
            "sentiment_trend": "无趋势",
            "decision_signals": [],
            "risk_flags": [],
        }

    llm = create_llm(temperature=0.2)
    interactions_text = json.dumps(interactions, ensure_ascii=False, indent=2)
    prompt = SENTIMENT_ANALYSIS_PROMPT.format(interactions=interactions_text)

    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        content = _clean_json(content)
        return json.loads(content)
    except Exception as e:
        logger.warning(f"情感分析失败: {e}")
        return _fallback_sentiment(interactions)


def _fallback_sentiment(interactions: list) -> dict:
    """简单的情感统计回退方案"""
    labels = [i.get("sentiment_label", "neutral") for i in interactions]
    pos = labels.count("positive")
    neg = labels.count("negative")
    if neg > pos:
        overall = "偏向负面"
        trend = "下滑"
    elif pos > neg:
        overall = "偏向正面"
        trend = "稳定"
    else:
        overall = "中性"
        trend = "平稳"

    risk_flags = []
    for i in interactions:
        if i.get("sentiment_label") == "negative":
            risk_flags.append(f"负面交互({i.get('timestamp','')}): {i.get('summary','')[:50]}")

    return {
        "overall_sentiment": overall,
        "sentiment_trend": trend,
        "decision_signals": [],
        "risk_flags": risk_flags,
    }


# ═══════════════════════════════════════════════════════════════
# Tool 3: 流失风险预测（规则 + LLM）
# ═══════════════════════════════════════════════════════════════

@tool
def predict_churn_risk(policies_json: str, sentiment_json: str, profile_json: str) -> dict:
    """预测客户流失风险，结合保单状态、情感分析和客户画像。

    Args:
        policies_json: JSON字符串，保单列表
        sentiment_json: JSON字符串，情感分析结果
        profile_json: JSON字符串，客户画像

    Returns:
        dict with keys: churn_risk (0-100), risk_level, risk_factors, key_time_nodes
    """
    from crm_agent.prompts import CHURN_PREDICTION_PROMPT

    policies = json.loads(policies_json) if isinstance(policies_json, str) else policies_json
    sentiment = json.loads(sentiment_json) if isinstance(sentiment_json, str) else sentiment_json

    # 规则层：基于保单状态计算基础风险分
    base_risk, risk_factors, time_nodes = _rule_based_churn(policies)

    # LLM层：结合情感数据增强预测
    llm = create_llm(temperature=0.2)
    context = json.dumps({
        "policies": policies,
        "sentiment_analysis": sentiment,
        "rule_based_risk": base_risk,
        "rule_risk_factors": risk_factors,
    }, ensure_ascii=False, indent=2)

    prompt = CHURN_PREDICTION_PROMPT.format(context=context)

    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        content = _clean_json(content)
        llm_result = json.loads(content)
        final_risk = llm_result.get("churn_risk", base_risk)
        return {
            "churn_risk": min(100, max(0, final_risk)),
            "risk_level": _risk_level(final_risk),
            "risk_factors": llm_result.get("risk_factors", risk_factors),
            "key_time_nodes": time_nodes,
            "recommended_actions": llm_result.get("recommended_actions", []),
        }
    except Exception as e:
        logger.warning(f"流失预测LLM失败: {e}")
        return {
            "churn_risk": base_risk,
            "risk_level": _risk_level(base_risk),
            "risk_factors": risk_factors,
            "key_time_nodes": time_nodes,
            "recommended_actions": ["联系客户确认续保意愿", "提供续保优惠方案"],
        }


def _rule_based_churn(policies: list) -> tuple:
    """规则引擎：保单状态 → 基础流失风险 + 关键时间节点"""
    risk = 0
    factors = []
    time_nodes = []
    now = datetime.now()

    expired_count = 0
    expiring_count = 0

    for p in policies:
        status = p.get("status", "active")
        end_str = p.get("end_date", "")

        if status == "expired":
            expired_count += 1
            risk += 25
            factors.append(f"保单「{p.get('product_name','')}」已过期未续保")

        elif status == "expiring_soon":
            expiring_count += 1
            risk += 15
            factors.append(f"保单「{p.get('product_name','')}」即将到期")
            try:
                end_date = datetime.strptime(end_str, "%Y-%m-%d")
                days_left = (end_date - now).days
                time_nodes.append({
                    "type": "续保提醒",
                    "policy_name": p.get("product_name", ""),
                    "date": end_str,
                    "days_left": days_left,
                    "urgency": "high" if days_left < 15 else "medium",
                })
            except (ValueError, TypeError):
                pass

        elif status == "active":
            try:
                end_date = datetime.strptime(end_str, "%Y-%m-%d")
                days_left = (end_date - now).days
                if 0 < days_left <= 60:
                    time_nodes.append({
                        "type": "续保提醒",
                        "policy_name": p.get("product_name", ""),
                        "date": end_str,
                        "days_left": days_left,
                        "urgency": "low",
                    })
            except (ValueError, TypeError):
                pass

        # 已发生理赔的保单也需要跟进
        if status == "claimed":
            time_nodes.append({
                "type": "理赔跟进",
                "policy_name": p.get("product_name", ""),
                "date": end_str,
                "days_left": 0,
                "urgency": "medium",
            })

    if expired_count >= 2:
        risk += 10
        factors.append("多份保单已过期，客户可能已流失")

    # 上限 100
    return min(100, risk), factors, time_nodes


def _risk_level(score: int) -> str:
    if score >= 60:
        return "high"
    elif score >= 30:
        return "medium"
    return "low"


# ═══════════════════════════════════════════════════════════════
# Tool 4: 加购机会识别
# ═══════════════════════════════════════════════════════════════

@tool
def identify_upsell_opportunities(profile_json: str, policies_json: str) -> list[dict]:
    """分析客户保单缺口，识别加购/升级机会。

    Args:
        profile_json: JSON字符串，客户画像
        policies_json: JSON字符串，现有保单列表

    Returns:
        list of dicts: 每个加购机会包含 product_type, reason, priority, estimated_premium
    """
    _profile = json.loads(profile_json) if isinstance(profile_json, str) else profile_json
    policies = json.loads(policies_json) if isinstance(policies_json, str) else policies_json

    # 获取已有险种
    existing_types = {p.get("insurance_type", "") for p in policies if p.get("status") != "expired"}

    # 险种覆盖推荐矩阵
    all_types = {
        "重疾险": {"reason": "重大疾病保障是家庭财务安全的核心", "priority": "high", "estimated_premium": "3000-8000元/年"},
        "医疗险": {"reason": "补充社保不足，应对高额医疗费用", "priority": "high", "estimated_premium": "200-2000元/年"},
        "意外险": {"reason": "覆盖意外风险，保费低杠杆高", "priority": "medium", "estimated_premium": "100-1000元/年"},
        "寿险": {"reason": "为家庭成员提供经济保障", "priority": "medium", "estimated_premium": "2000-10000元/年"},
        "年金险": {"reason": "养老规划，锁定长期收益", "priority": "low", "estimated_premium": "10000-50000元/年"},
        "车险": {"reason": "车辆上路必备保障", "priority": "low", "estimated_premium": "2000-6000元/年"},
    }

    opportunities = []
    for ins_type, info in all_types.items():
        if ins_type not in existing_types:
            opportunities.append({
                "product_type": ins_type,
                "reason": info["reason"],
                "priority": info["priority"],
                "estimated_premium": info["estimated_premium"],
            })

    # 已有险种的升级建议
    for p in policies:
        if p.get("status") == "active":
            ins_type = p.get("insurance_type", "")
            if ins_type == "重疾险" and p.get("insured_amount", 0) < 300000:
                opportunities.append({
                    "product_type": f"升级{ins_type}",
                    "reason": f"当前保额{p.get('insured_amount', 0)/10000:.0f}万偏低，建议升级保障额度",
                    "priority": "medium",
                    "estimated_premium": "额外+2000-5000元/年",
                })

    # 按优先级排序
    priority_order = {"high": 0, "medium": 1, "low": 2}
    opportunities.sort(key=lambda x: priority_order.get(x["priority"], 9))

    return opportunities


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def _clean_json(content: str) -> str:
    """清理LLM输出中的JSON标记"""
    import re
    content = content.strip()
    # 去掉markdown代码块
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n?", "", content)
        content = re.sub(r"\n```$", "", content)
    # 提取第一个JSON对象
    match = re.search(r'\{[\s\S]*\}', content)
    if match:
        return match.group(0)
    return content
