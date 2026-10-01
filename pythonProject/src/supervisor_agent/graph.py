"""Supervisor graph that routes requests to existing child agents."""

import json
import logging
from functools import lru_cache
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from crm_agent.graph import build_graph as build_crm_graph
from insurance_agent.config import create_llm
from insurance_agent.graph import build_graph as build_insurance_graph
from knowledge_agent.graph import build_graph as build_knowledge_graph
from supervisor_agent.state import AgentRoute, SupervisorAgentState
logger = logging.getLogger(__name__)

_store_ref: Any = None


# ─── helpers (must be defined before build_graph) ───────────

def _clear_child_graph_cache() -> None:
    _get_insurance_graph.cache_clear()
    _get_knowledge_graph.cache_clear()
    _get_crm_graph.cache_clear()


def _latest_user_text(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, dict):
            role = msg.get("role", msg.get("type", ""))
            if role in ("user", "human"):
                return str(msg.get("content", ""))
        elif getattr(msg, "type", "") == "human":
            return str(getattr(msg, "content", ""))
    return ""


def _rule_route(question: str) -> AgentRoute | None:
    text = question.lower()
    crm_keywords = (
        "crm", "客户关系", "客户分析", "流失", "续保", "加购", "复购",
        "客户画像", "保单提醒", "销售跟进", "用户crm",
    )
    recommend_intent_keywords = (
        "推荐", "适合我", "怎么买", "买什么", "配置", "方案", "想买",
        "我要买", "帮我选", "投保建议",
    )
    personal_need_keywords = (
        "预算", "岁", "年龄", "职业", "程序员", "教师", "销售", "设计师",
    )

    if any(keyword in text for keyword in crm_keywords):
        return "crm_agent"
    if any(keyword in text for keyword in recommend_intent_keywords):
        return "insurance_agent"
    if "保险" in text and any(keyword in text for keyword in personal_need_keywords):
        return "insurance_agent"
    return None


def _describe_child_result(result: dict, child_name: str) -> str:
    """Generate a human-readable summary when child agent returns no final answer."""
    if child_name == "insurance_agent":
        profile = result.get("user_profile")
        if profile:
            return (
                f"已为您提取画像：{profile.age}岁，{profile.occupation}，"
                f"预算{profile.budget}元/年，意向{profile.insurance_type}。"
                f"但未找到完全匹配的产品，建议调整预算或险种条件后重试。"
            )
        return "🔔 系统需要您补充年龄、职业、预算和意向险种信息，才能为您精准推荐保险产品。"

    if child_name == "knowledge_agent":
        return "知识库暂未检索到相关内容，请尝试换个方式提问。"

    if child_name == "crm_agent":
        churn = result.get("churn_risk", "?")
        return f"CRM 分析完成，流失风险评分 {churn}/100，详细信息请查看报告。"

    return f"{child_name} 已完成分析。"


def _parse_json_object(content: str) -> dict:
    text = content.strip()
    # 去掉 markdown 代码块
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    # 去掉 markdown 粗体标记（偶尔 LLM 用 **insurance_agent**）
    text = text.replace("**", "")
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _child_input(state: SupervisorAgentState) -> dict:
    data = {"messages": state.get("messages", [])}
    if state.get("user_id"):
        data["user_id"] = state["user_id"]
    return data


def _child_config(config: RunnableConfig | None, child_name: str) -> RunnableConfig:
    parent_config = (config or {}).get("configurable", {})
    parent_thread_id = parent_config.get("thread_id", "default")
    child_config: RunnableConfig = {
        "configurable": {
            "thread_id": f"{parent_thread_id}:{child_name}",
        }
    }
    if parent_config.get("user_id"):
        child_config["configurable"]["user_id"] = parent_config["user_id"]
    return child_config


def _child_output(result: dict, child_name: str, answer_key: str) -> dict:
    answer = result.get(answer_key) or _extract_message_reply(result)
    if not answer:
        # 子 agent 可能被 interrupt 中断（如缺失字段），给出友好提示
        answer = _describe_child_result(result, child_name)
    return {
        "child_result": result,
        "final_answer": answer or str(result),
        "handled_by": child_name,
    }


def _extract_message_reply(result: dict) -> str:
    messages = result.get("messages", [])
    if not messages:
        return ""
    last_msg = messages[-1]
    if hasattr(last_msg, "content"):
        content = last_msg.content
    elif isinstance(last_msg, dict):
        content = last_msg.get("content", "")
    else:
        content = str(last_msg)
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


@lru_cache(maxsize=1)
def _get_insurance_graph():
    return build_insurance_graph(store=_store_ref)


@lru_cache(maxsize=1)
def _get_knowledge_graph():
    return build_knowledge_graph(store=_store_ref)


@lru_cache(maxsize=1)
def _get_crm_graph():
    return build_crm_graph()


# ─── ROUTE_PROMPT ───────────────────────────────────────────

ROUTE_PROMPT = """你是一个保险服务多智能体系统的路由网关。
请将用户的最新请求精准分类到以下某一个子智能体中。

可用的子智能体：
- insurance_agent（保险顾问）：负责保险产品推荐、方案匹配，以及基于年龄、职业、预算、险种提供的购买建议。
- knowledge_agent（知识库）：负责保险知识问答、产品条款、等待期、理赔规则、价格/保额/资产查询以及常规名词解释。
- crm_agent（客户管理）：负责客户 CRM 分析、客户画像/报告、流失风险评估、续保提醒、二次开拓机会（客情维护）以及保单/客户关系管理。

请仅返回 JSON 格式数据：
{"route":"insurance_agent|knowledge_agent|crm_agent","reason":"简短的分类理由"}

用户请求：
{question}
"""


# ─── nodes ──────────────────────────────────────────────────

async def route_request_node(state: SupervisorAgentState) -> dict:
    """Choose which child agent should handle the latest user request."""
    question = _latest_user_text(state.get("messages", []))

    route = _rule_route(question)
    reason = "matched local routing rules"

    if route is None:
        route = "knowledge_agent"
        reason = "defaulted to knowledge_agent"
        try:
            llm = create_llm(temperature=0)
            response = llm.invoke(ROUTE_PROMPT.format(question=question))
            content = response.content if hasattr(response, "content") else str(response)
            parsed = _parse_json_object(content)
            llm_route = parsed.get("route", "")
            # 清理可能的空白和特殊字符
            llm_route = str(llm_route).strip().strip('"').strip("'")
            if llm_route in ("insurance_agent", "knowledge_agent", "crm_agent"):
                route = llm_route
                reason = str(parsed.get("reason", "classified by LLM"))
        except Exception:
            pass  # 规则路由已经覆盖了主要场景，LLM 失败静默处理

    return {"route": route, "route_reason": reason}


async def call_insurance_agent_node(
    state: SupervisorAgentState,
    config: RunnableConfig | None = None,
) -> dict:
    """Run the insurance recommendation child graph."""
    graph = _get_insurance_graph()
    try:
        result = await graph.ainvoke(
            _child_input(state),
            _child_config(config, "insurance_agent"),
        )
    except Exception:
        # interrupt() 抛出的中断（如缺少年龄/职业等必填字段）
        return {
            "handled_by": "insurance_agent",
            "final_answer": "需要您补充年龄、职业、预算和意向险种信息，才能为您精准推荐保险产品。",
        }
    return _child_output(result, "insurance_agent", "final_recommendation")


async def call_knowledge_agent_node(
    state: SupervisorAgentState,
    config: RunnableConfig | None = None,
) -> dict:
    """Run the knowledge Q&A child graph."""
    graph = _get_knowledge_graph()
    try:
        result = await graph.ainvoke(
            _child_input(state),
            _child_config(config, "knowledge_agent"),
        )
    except Exception:
        return {
            "handled_by": "knowledge_agent",
            "final_answer": "知识库暂未检索到相关内容，请尝试换个方式提问。",
        }
    return _child_output(result, "knowledge_agent", "final_answer")


async def call_crm_agent_node(
    state: SupervisorAgentState,
    config: RunnableConfig | None = None,
) -> dict:
    """Run the CRM child graph."""
    graph = _get_crm_graph()
    try:
        result = await graph.ainvoke(
            _child_input(state),
            _child_config(config, "crm_agent"),
        )
    except Exception:
        return {
            "handled_by": "crm_agent",
            "final_answer": "CRM 分析遇到错误，请稍后重试。",
        }
    return _child_output(result, "crm_agent", "crm_report")


def route_to_child(state: SupervisorAgentState) -> str:
    route = state.get("route", "knowledge_agent")
    if route == "insurance_agent":
        return "call_insurance_agent"
    if route == "crm_agent":
        return "call_crm_agent"
    return "call_knowledge_agent"


def _describe_child_result(result: dict, child_name: str) -> str:
    """Generate a human-readable summary when child agent returns no final answer."""
    if child_name == "insurance_agent":
        profile = result.get("user_profile")
        if profile:
            return (
                f"已为您提取画像：{profile.age}岁，{profile.occupation}，"
                f"预算{profile.budget}元/年，意向{profile.insurance_type}。"
                f"但未找到完全匹配的产品，建议调整预算或险种条件后重试。"
            )
        return "需要您补充年龄、职业、预算和意向险种信息，才能为您精准推荐保险产品。"

    if child_name == "knowledge_agent":
        return "知识库暂未检索到相关内容，请尝试换个方式提问。"

    if child_name == "crm_agent":
        churn = result.get("churn_risk", "?")
        return f"CRM 分析完成，流失风险评分 {churn}/100，详细信息请查看报告。"

    return f"{child_name} 已完成分析。"


# ─── build ──────────────────────────────────────────────────

def build_graph(store=None):
    global _store_ref
    _store_ref = store
    _clear_child_graph_cache()

    workflow = StateGraph(SupervisorAgentState)
    workflow.add_node("route_request", route_request_node)
    workflow.add_node("call_insurance_agent", call_insurance_agent_node)
    workflow.add_node("call_knowledge_agent", call_knowledge_agent_node)
    workflow.add_node("call_crm_agent", call_crm_agent_node)

    workflow.set_entry_point("route_request")
    workflow.add_conditional_edges(
        "route_request",
        route_to_child,
        {
            "call_insurance_agent": "call_insurance_agent",
            "call_knowledge_agent": "call_knowledge_agent",
            "call_crm_agent": "call_crm_agent",
        },
    )
    workflow.add_edge("call_insurance_agent", END)
    workflow.add_edge("call_knowledge_agent", END)
    workflow.add_edge("call_crm_agent", END)

    return workflow.compile(checkpointer=MemorySaver())


graph = build_graph()
