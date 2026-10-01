"""
知识回答Agent — LangGraph 工作流（支持跨会话记忆）

流程设计：
  ┌──────────────────┐
  │ 0.load_user_context│  [NEW] 从 Store 加载用户画像/偏好
  └──────┬───────────┘
         ▼
  ┌──────────────┐
  │ 1.query_rewrite│  用户问题 + 历史消息 + 用户上下文 → LLM重写 → 完整问题
  └──────┬───────┘
         ▼
  ┌──────────────────┐
  │ 2.intent_recognition│  LLM判断意图 → "db" 或 "rag"
  └──────┬───────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────┐
│3.db_query│ │4.rag_search│
└───┬────┘ └────┬─────┘
    └─────┬─────┘
          ▼
  ┌──────────────────┐
  │5.generate_answer  │  DB结果/RAG结果 + 用户上下文 → LLM整理 → 最终解答
  └──────┬───────────┘
         ▼
  ┌──────────────────┐
  │6.save_interaction │ [NEW] 保存交互摘要到 Store
  └──────────────────┘
"""

from __future__ import annotations

import logging
import json
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, ConfigDict

from harness.dependencies import AgentDependencies
from knowledge_agent.state import KnowledgeAgentState
from knowledge_agent.tools import (
    rewrite_question,
    recognize_intent,
    query_db_by_intent,
    search_rag,
    generate_db_answer,
    generate_rag_answer,
)
from middleware.model import ModelCallContext, ModelRequest
from tools.base import ToolCallContext
from tools.product_tools import ProductSearchInput

logger = logging.getLogger(__name__)


class IntentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["db", "rag"]

# ═══════════════════════════════════════════════════════════════════════════════
# Node 0: 从 Store 加载用户上下文
# ═══════════════════════════════════════════════════════════════════════════════
# 目的：在问题重写前，加载用户的完整上下文（画像 + 偏好 + 近期交互）
# 这样 LLM 重写问题时可以结合用户已知信息，做出更精准的指代消解

async def load_user_context_node(
    state: KnowledgeAgentState,
    *,
    store: Any = None,
) -> dict:
    """从 PostgreSQL Store 加载用户上下文。

    加载内容包括：
    - 用户画像（年龄/职业/预算/险种偏好）
    - 用户偏好（关注的险种、产品）
    - 近期交互摘要（上次问了什么、推荐了什么）

    这些信息会传递给 query_rewrite 节点，帮助 LLM 理解"它"指代什么。
    """
    user_id = state.get("user_id", "")
    if not user_id or store is None:
        return {"user_context": {"is_new_user": True}}

    try:
        from shared.memory import UserMemoryStore
        memory = UserMemoryStore(store)
        context = await memory.load_user_context(user_id)
        logger.info(f"用户 {user_id} 上下文已加载: is_new={context.get('is_new_user')}")
        return {"user_context": context}
    except Exception as e:
        logger.warning(f"加载用户上下文失败: {e}")
        return {"user_context": {"is_new_user": True}}


# ═══════════════════════════════════════════════════════════════════════════════
# Node 1: 问题重写（增强版：含用户上下文）
# ═══════════════════════════════════════════════════════════════════════════════

async def query_rewrite_node(state: KnowledgeAgentState) -> dict:
    """将对话历史和用户上下文结合，用LLM重写为语义完整的问题。

    增强点：如果 Store 中有用户画像和近期交互，会作为额外上下文
    传给 LLM，帮助理解"它"、"这款产品"等指代。
    例如：
    - 用户1在会话1中了解了"安心保·重疾险"
    - 新会话中问"它的等待期是多久？"
    - 上下文告诉LLM用户最近在了解"安心保·重疾险"
    - LLM重写为"安心保·重疾险（标准版）的等待期是多久？"
    """
    messages = state.get("messages", [])
    user_context = state.get("user_context", {})

    # 获取用户输入的原始问题（取最后一条human/user消息）
    raw_question = ""
    for msg in reversed(messages):
        if isinstance(msg, dict):
            role = msg.get("role", msg.get("type", ""))
            if role in ("human", "user"):
                raw_question = msg.get("content", str(msg))
                break
        else:
            if getattr(msg, "type", "") == "human":
                raw_question = getattr(msg, "content", str(msg))
                break

    # 格式化对话历史
    history = _format_history(messages[:-1]) if len(messages) > 1 else ""

    # 增强：如果有用户上下文，追加到历史中帮助LLM做指代消解
    if user_context and not user_context.get("is_new_user"):
        profile = user_context.get("profile", {})
        if profile:
            profile_hint = (
                f"[系统备注：该用户已知信息——"
                f"年龄{profile.get('age', '?')}岁，"
                f"职业{profile.get('occupation', '?')}，"
                f"预算{profile.get('budget', '?')}元/年，"
                f"关注{profile.get('insurance_type', '?')}]"
            )
            history = profile_hint + "\n" + history if history else profile_hint

    # 执行重写
    rewritten = rewrite_question(history, raw_question)

    return {
        "raw_question": raw_question,
        "rewritten_question": rewritten,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Node 2: 意图识别
# ═══════════════════════════════════════════════════════════════════════════════

async def intent_recognition_node(state: KnowledgeAgentState) -> dict:
    """判断问题意图：数据库查询 还是 知识库检索。"""
    question = state.get("rewritten_question", "") or state.get("raw_question", "")
    intent = recognize_intent(question)
    return {"intent": intent}


# ═══════════════════════════════════════════════════════════════════════════════
# Node 3: 数据库查询
# ═══════════════════════════════════════════════════════════════════════════════

async def db_query_node(state: KnowledgeAgentState) -> dict:
    """执行数据库精确查询，获取产品结构化属性。"""
    question = state.get("rewritten_question", "")
    db_results = query_db_by_intent(question)
    return {"db_results": db_results}


# ═══════════════════════════════════════════════════════════════════════════════
# Node 4: RAG知识库检索
# ═══════════════════════════════════════════════════════════════════════════════

async def rag_search_node(state: KnowledgeAgentState) -> dict:
    """在多个知识库collection中检索相关内容。"""
    question = state.get("rewritten_question", "")
    rag_docs = search_rag(question)
    return {"rag_docs": rag_docs}


# ═══════════════════════════════════════════════════════════════════════════════
# Node 5: 生成最终知识解答
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_answer_node(state: KnowledgeAgentState) -> dict:
    """根据意图类型，将DB或RAG的查询结果喂给LLM生成自然语言回答。"""
    question = state.get("rewritten_question", "") or state.get("raw_question", "")
    intent = state.get("intent", "rag")

    if intent == "db":
        db_results = state.get("db_results", [])
        answer = generate_db_answer(question, db_results)
    else:
        rag_docs = state.get("rag_docs", [])
        answer = generate_rag_answer(question, rag_docs)

    return {"final_answer": answer}


# ═══════════════════════════════════════════════════════════════════════════════
# Node 6: 保存交互摘要到 Store
# ═══════════════════════════════════════════════════════════════════════════════

async def save_interaction_node(
    state: KnowledgeAgentState,
    *,
    store: Any = None,
) -> dict:
    """将本次知识问答的摘要保存到 Store，供后续会话参考。

    保存内容：
    - 问题摘要
    - 意图类型
    - 回答预览
    - 涉及的产品ID（如果有）
    """
    user_id = state.get("user_id", "")
    if not user_id or store is None:
        return {}

    try:
        from shared.memory import UserMemoryStore
        memory = UserMemoryStore(store)

        # 提取涉及的产品ID
        product_ids = []
        db_results = state.get("db_results", [])
        if db_results:
            product_ids = [p.get("product_id", "") for p in db_results[:5]]

        await memory.save_interaction(user_id, {
            "type": "qa",
            "agent": "knowledge_agent",
            "question": state.get("raw_question", "")[:200],
            "intent": state.get("intent", ""),
            "product_ids": product_ids,
            "answer_preview": state.get("final_answer", "")[:200],
        })
        logger.info(f"用户 {user_id} 知识问答交互摘要已保存")
    except Exception as e:
        logger.warning(f"保存交互摘要失败: {e}")

    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# 条件路由
# ═══════════════════════════════════════════════════════════════════════════════

def route_by_intent(state: KnowledgeAgentState) -> Literal["db_query", "rag_search"]:
    intent = state.get("intent", "rag")
    if intent == "db":
        return "db_query"
    return "rag_search"


# ═══════════════════════════════════════════════════════════════════════════════
# 构建并编译工作流图
# ═══════════════════════════════════════════════════════════════════════════════

def build_graph(*, checkpointer=None, store=None, dependencies: AgentDependencies | None = None):
    """构建知识回答Agent的LangGraph工作流。

    节点拓扑：
    load_user_context → query_rewrite → intent_recognition
                     ─┬→ db_query ─┬→ generate_answer → save_interaction → END
                      └→ rag_search ┘

    Args:
        store: 可选的 BaseStore 实例。传入时启用跨会话上下文加载和交互保存。
    """
    workflow = StateGraph(KnowledgeAgentState)

    async def load_context(state: KnowledgeAgentState) -> dict:
        return await load_user_context_node(state, store=store)

    async def save_interaction(state: KnowledgeAgentState) -> dict:
        return await save_interaction_node(state, store=store)

    async def governed_query_rewrite(
        state: KnowledgeAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        if dependencies is None or dependencies.model_gateway is None:
            return await query_rewrite_node(state)
        messages = state.get("messages", [])
        raw_question = _latest_user_text(messages)
        history = _format_history(messages[:-1]) if len(messages) > 1 else ""
        user_context = state.get("user_context", {})
        if user_context and not user_context.get("is_new_user"):
            history = f"{json.dumps(user_context, ensure_ascii=False)}\n{history}"
        try:
            result = await dependencies.model_gateway.invoke(
                ModelRequest(
                    prompt_id="knowledge.rewrite",
                    variables={"history": history, "question": raw_question},
                    strategy="extract",
                ),
                context=ModelCallContext.from_config(config),
            )
            rewritten = result.data
        except Exception:
            rewritten = raw_question
        return {"raw_question": raw_question, "rewritten_question": rewritten}

    async def governed_intent(
        state: KnowledgeAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        if dependencies is None or dependencies.model_gateway is None:
            return await intent_recognition_node(state)
        question = state.get("rewritten_question", "") or state.get("raw_question", "")
        try:
            result = await dependencies.model_gateway.invoke(
                ModelRequest(
                    prompt_id="knowledge.intent",
                    variables={"question": question},
                    strategy="classify",
                    response_model=IntentDecision,
                ),
                context=ModelCallContext.from_config(config),
            )
            return {"intent": result.data.intent}
        except Exception:
            return {"intent": "rag"}

    async def governed_db_query(
        state: KnowledgeAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        if (
            dependencies is None
            or dependencies.model_gateway is None
            or dependencies.tool_gateway is None
        ):
            return await db_query_node(state)
        question = state.get("rewritten_question", "")
        parsed = await dependencies.model_gateway.invoke(
            ModelRequest(
                prompt_id="knowledge.query",
                variables={"question": question},
                strategy="extract",
                response_model=ProductSearchInput,
            ),
            context=ModelCallContext.from_config(config),
        )
        result = await dependencies.tool_gateway.execute(
            "search_active_insurance_products",
            parsed.data.model_dump(exclude_none=True),
            context=ToolCallContext.from_config(config),
        )
        return {"db_results": result.data}

    async def governed_rag_search(
        state: KnowledgeAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        if dependencies is None or dependencies.tool_gateway is None:
            return await rag_search_node(state)
        result = await dependencies.tool_gateway.execute(
            "retrieve_policy_evidence",
            {
                "query": state.get("rewritten_question", ""),
                "product_ids": [],
                "top_k": 10,
            },
            context=ToolCallContext.from_config(config),
        )
        return {"rag_docs": result.data}

    async def governed_answer(
        state: KnowledgeAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        if dependencies is None or dependencies.model_gateway is None:
            return await generate_answer_node(state)
        question = state.get("rewritten_question", "") or state.get("raw_question", "")
        evidence = state.get("db_results", []) if state.get("intent") == "db" else state.get("rag_docs", [])
        if not evidence:
            return {"final_answer": "当前没有检索到可验证的资料，暂时无法给出可靠结论。"}
        result = await dependencies.model_gateway.invoke(
            ModelRequest(
                prompt_id="knowledge.answer",
                variables={
                    "question": question,
                    "intent": state.get("intent", "rag"),
                    "evidence": json.dumps(evidence, ensure_ascii=False),
                },
                strategy="aggregate",
            ),
            context=ModelCallContext.from_config(config),
        )
        return {"final_answer": result.data}

    # ── 注册所有节点 ──
    workflow.add_node("load_user_context", load_context)
    workflow.add_node("query_rewrite", governed_query_rewrite)
    workflow.add_node("intent_recognition", governed_intent)
    workflow.add_node("db_query", governed_db_query)
    workflow.add_node("rag_search", governed_rag_search)
    workflow.add_node("generate_answer", governed_answer)
    workflow.add_node("save_interaction", save_interaction)

    # ── 入口 ──
    workflow.set_entry_point("load_user_context")

    # ── 边 ──
    workflow.add_edge("load_user_context", "query_rewrite")
    workflow.add_edge("query_rewrite", "intent_recognition")

    workflow.add_conditional_edges(
        "intent_recognition",
        route_by_intent,
        {"db_query": "db_query", "rag_search": "rag_search"},
    )

    workflow.add_edge("db_query", "generate_answer")
    workflow.add_edge("rag_search", "generate_answer")
    workflow.add_edge("generate_answer", "save_interaction")
    workflow.add_edge("save_interaction", END)

    return workflow.compile(checkpointer=checkpointer, store=store)


# langgraph.json 的无持久化定义；正式 HTTP 入口由 lifespan 注入 PostgreSQL。
graph = build_graph()


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def _format_history(messages: list) -> str:
    """将消息列表格式化为对话历史文本，兼容 dict 和 LangChain 对象。"""
    if not messages:
        return ""
    lines = []
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get("role", msg.get("type", "unknown"))
            content = msg.get("content", str(msg))
        else:
            role = getattr(msg, "type", "unknown")
            content = getattr(msg, "content", str(msg))
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        role_label = "用户" if role in ("human", "user") else ("助手" if role in ("ai", "assistant") else role)
        lines.append(f"{role_label}: {content}")
    return "\n".join(lines)


def _latest_user_text(messages: list) -> str:
    for message in reversed(messages):
        if isinstance(message, dict):
            if message.get("role", message.get("type")) in ("user", "human"):
                return str(message.get("content", ""))
        elif getattr(message, "type", "") == "human":
            return str(getattr(message, "content", ""))
    return ""
