"""Supervisor graph that routes requests to existing child agents."""

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, ConfigDict

from crm_agent.graph import build_graph as build_crm_graph
from harness.dependencies import AgentDependencies
from insurance_agent.config import create_llm as create_llm  # backward-compatible test seam
from insurance_agent.graph import build_graph as build_insurance_graph
from knowledge_agent.graph import build_graph as build_knowledge_graph
from middleware.model import ModelCallContext, ModelRequest
from supervisor_agent.state import AgentRoute, SupervisorAgentState
from workflows.family_plan import build_family_plan_graph
logger = logging.getLogger(__name__)

# ─── helpers (must be defined before build_graph) ───────────

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
    family_keywords = (
        "家庭保障",
        "家庭保险",
        "全家保障",
        "全家保险",
        "家庭规划",
        "家庭方案",
        "一家人",
    )
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

    if any(keyword in text for keyword in family_keywords):
        return "family_plan"
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


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: AgentRoute
    reason: str


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
            **parent_config,
            "thread_id": f"{parent_thread_id}:{child_name}",
        }
    }
    return child_config


def _child_output(result: dict, child_name: str, answer_key: str) -> dict:
    answer = result.get(answer_key) or _extract_message_reply(result)
    if not answer:
        # 子 agent 可能被 interrupt 中断（如缺失字段），给出友好提示
        answer = _describe_child_result(result, child_name)
    return {
        "child_result": result,
        "final_answer": answer or str(result),
        "handled_by": result.get("handled_by") or child_name,
        "warnings": result.get("warnings", []),
        "citations": result.get("citations", []),
    }


async def _invoke_child_with_interrupts(
    graph: Any,
    input_data: dict[str, Any],
    config: RunnableConfig,
) -> dict[str, Any]:
    """Propagate child interrupts to the parent and resume the same child thread."""

    result = await graph.ainvoke(input_data, config)
    while result.get("__interrupt__"):
        child_interrupt = result["__interrupt__"][0]
        resume_payload = interrupt(getattr(child_interrupt, "value", child_interrupt))
        result = await graph.ainvoke(Command(resume=resume_payload), config)
    return result


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


def _get_insurance_graph(*, checkpointer=None, store=None, dependencies=None):
    return build_insurance_graph(
        checkpointer=checkpointer,
        store=store,
        dependencies=dependencies,
    )


def _get_knowledge_graph(*, checkpointer=None, store=None, dependencies=None):
    return build_knowledge_graph(
        checkpointer=checkpointer,
        store=store,
        dependencies=dependencies,
    )


def _get_crm_graph(*, checkpointer=None, store=None, dependencies=None):
    return build_crm_graph(
        checkpointer=checkpointer,
        store=store,
        dependencies=dependencies,
    )


def _get_family_plan_graph(*, checkpointer=None, store=None, dependencies=None):
    registry = dependencies.agent_registry if dependencies is not None else None
    return build_family_plan_graph(
        dependencies=dependencies,
        registry=registry,
        checkpointer=checkpointer,
        store=store,
    )


# ─── ROUTE_PROMPT ───────────────────────────────────────────

ROUTE_PROMPT = """你是一个保险服务多智能体系统的路由网关。
请将用户的最新请求精准分类到以下某一个子智能体中。

可用的子智能体：
- insurance_agent（保险顾问）：负责保险产品推荐、方案匹配，以及基于年龄、职业、预算、险种提供的购买建议。
- knowledge_agent（知识库）：负责保险知识问答、产品条款、等待期、理赔规则、价格/保额/资产查询以及常规名词解释。
- crm_agent（客户管理）：负责客户 CRM 分析、客户画像/报告、流失风险评估、续保提醒、二次开拓机会（客情维护）以及保单/客户关系管理。
- family_plan（家庭保障规划）：组合画像、现有保单、保障缺口、产品、知识和合规检查。

请仅返回 JSON 格式数据：
{"route":"insurance_agent|knowledge_agent|crm_agent|family_plan","reason":"简短的分类理由"}

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

    return {"route": route, "route_reason": reason}


async def _governed_route_request_node(
    state: SupervisorAgentState,
    config: RunnableConfig | None,
    dependencies: AgentDependencies,
) -> dict:
    question = _latest_user_text(state.get("messages", []))
    route = _rule_route(question)
    if route is not None:
        return {"route": route, "route_reason": "matched local routing rules"}
    if dependencies.model_gateway is None:
        return await route_request_node(state)
    try:
        result = await dependencies.model_gateway.invoke(
            ModelRequest(
                prompt_id="supervisor.route",
                variables={"question": question},
                strategy="route",
                response_model=RouteDecision,
            ),
            context=ModelCallContext.from_config(config),
        )
        decision: RouteDecision = result.data
        return {"route": decision.route, "route_reason": decision.reason}
    except Exception:
        return {"route": "knowledge_agent", "route_reason": "safe routing fallback"}


async def call_insurance_agent_node(
    state: SupervisorAgentState,
    config: RunnableConfig | None = None,
    *,
    graph: Any = None,
) -> dict:
    """Run the insurance recommendation child graph."""
    child_graph = graph or _get_insurance_graph()
    result = await _invoke_child_with_interrupts(
        child_graph,
        _child_input(state),
        _child_config(config, "insurance_agent"),
    )
    return _child_output(result, "insurance_agent", "final_recommendation")


async def call_knowledge_agent_node(
    state: SupervisorAgentState,
    config: RunnableConfig | None = None,
    *,
    graph: Any = None,
) -> dict:
    """Run the knowledge Q&A child graph."""
    child_graph = graph or _get_knowledge_graph()
    result = await _invoke_child_with_interrupts(
        child_graph,
        _child_input(state),
        _child_config(config, "knowledge_agent"),
    )
    return _child_output(result, "knowledge_agent", "final_answer")


async def call_crm_agent_node(
    state: SupervisorAgentState,
    config: RunnableConfig | None = None,
    *,
    graph: Any = None,
) -> dict:
    """Run the CRM child graph."""
    child_graph = graph or _get_crm_graph()
    result = await _invoke_child_with_interrupts(
        child_graph,
        _child_input(state),
        _child_config(config, "crm_agent"),
    )
    return _child_output(result, "crm_agent", "crm_report")


async def call_family_plan_node(
    state: SupervisorAgentState,
    config: RunnableConfig | None = None,
    *,
    graph: Any = None,
) -> dict:
    """Run the composable family protection planning graph."""
    child_graph = graph or _get_family_plan_graph()
    result = await _invoke_child_with_interrupts(
        child_graph,
        _child_input(state),
        _child_config(config, "family_plan"),
    )
    return _child_output(result, "family_plan", "final_answer")


def route_to_child(state: SupervisorAgentState) -> str:
    route = state.get("route", "knowledge_agent")
    if route == "insurance_agent":
        return "call_insurance_agent"
    if route == "crm_agent":
        return "call_crm_agent"
    if route == "family_plan":
        return "call_family_plan"
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

def build_graph(*, checkpointer=None, store=None, dependencies: AgentDependencies | None = None):
    workflow = StateGraph(SupervisorAgentState)
    insurance_graph = _get_insurance_graph(
        checkpointer=checkpointer,
        store=store,
        dependencies=dependencies,
    )
    knowledge_graph = _get_knowledge_graph(
        checkpointer=checkpointer,
        store=store,
        dependencies=dependencies,
    )
    crm_graph = _get_crm_graph(
        checkpointer=checkpointer,
        store=store,
        dependencies=dependencies,
    )
    family_plan_graph = _get_family_plan_graph(
        checkpointer=checkpointer,
        store=store,
        dependencies=dependencies,
    )

    async def route_request(
        state: SupervisorAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        if dependencies is None:
            return await route_request_node(state)
        return await _governed_route_request_node(state, config, dependencies)

    async def call_insurance(
        state: SupervisorAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        return await call_insurance_agent_node(state, config, graph=insurance_graph)

    async def call_knowledge(
        state: SupervisorAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        return await call_knowledge_agent_node(state, config, graph=knowledge_graph)

    async def call_crm(
        state: SupervisorAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        return await call_crm_agent_node(state, config, graph=crm_graph)

    async def call_family_plan(
        state: SupervisorAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        return await call_family_plan_node(state, config, graph=family_plan_graph)

    workflow.add_node("route_request", route_request)
    workflow.add_node("call_insurance_agent", call_insurance)
    workflow.add_node("call_knowledge_agent", call_knowledge)
    workflow.add_node("call_crm_agent", call_crm)
    workflow.add_node("call_family_plan", call_family_plan)

    workflow.set_entry_point("route_request")
    workflow.add_conditional_edges(
        "route_request",
        route_to_child,
        {
            "call_insurance_agent": "call_insurance_agent",
            "call_knowledge_agent": "call_knowledge_agent",
            "call_crm_agent": "call_crm_agent",
            "call_family_plan": "call_family_plan",
        },
    )
    workflow.add_edge("call_insurance_agent", END)
    workflow.add_edge("call_knowledge_agent", END)
    workflow.add_edge("call_crm_agent", END)
    workflow.add_edge("call_family_plan", END)

    return workflow.compile(checkpointer=checkpointer, store=store)


# langgraph.json 的无持久化定义；正式 HTTP 入口由 lifespan 注入 PostgreSQL。
graph = build_graph()
