"""Insurance recommendation agent — LangGraph workflow with cross-session memory.

Workflow:
0. Load user historical profile from Store (跨会话记忆，作为 LLM 参考)
1. Extract user profile from conversation (LLM) — 结合用户本次输入 + Store 历史画像
2. Validate required fields → interrupt() if missing
3. MySQL strict query for matching products
4. RAG enrichment for product context
5. Generate final recommendation with reasoning
6. [NEW] Save user profile to Store (跨会话记忆)
"""

import json
import logging
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt

from harness.dependencies import AgentDependencies
from harness.errors import DependencyUnavailableError
from insurance_agent.state import (
    InsuranceAgentState,
    REQUIRED_FIELDS,
    UserProfile,
)
from insurance_agent.prompts import (
    MISSING_FIELDS_PROMPT,
)
from insurance_agent.tools import (
    extract_user_profile,
    query_insurance_products_mysql,
    rag_enrich_products,
    validate_user_profile,
)
from middleware.model import ModelCallContext, ModelRequest
from tools.base import ToolCallContext

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Node 0: 从 Store 加载历史画像作为 LLM 提取的参考上下文
# ═══════════════════════════════════════════════════════════════════════════════
# 目的：新会话开始时，先查 PG Store 是否有该用户的历史画像
# 无论是否有历史画像，都进入 LLM 提取流程
# 历史画像作为参考上下文传给 LLM，但以用户本次输入为准

async def load_profile_from_store(
    state: InsuranceAgentState,
    *,
    store: Any = None,
) -> dict:
    """从 PostgreSQL Store 加载历史用户画像，作为 LLM 提取的参考上下文。

    场景：
    - 用户A在会话1中说"28岁，程序员，预算5000"
    - 用户A新开会话2，从 Store 加载历史画像作为参考
    - 无论是否加载到，都进入 LLM 提取流程，历史画像作为上下文一起发给 LLM
    - LLM 以用户本次输入为准，历史画像仅作参考

    策略变更（2024）：
    - 旧策略：Store 有完整画像则直接使用，跳过 LLM 提取
    - 新策略：Store 画像仅作为参考上下文，每次都走 LLM 提取
    - 冲突规则：用户本次输入与历史画像冲突时，以用户本次输入为准
    """
    user_id = state.get("user_id", "")
    if not user_id or store is None:
        return {}

    try:
        from shared.memory import UserMemoryStore
        memory = UserMemoryStore(store)
        stored_profile = await memory.load_user_profile(user_id)

        if stored_profile:
            logger.info(f"用户 {user_id} 历史画像从 Store 加载成功，作为 LLM 参考上下文")
            return {"stored_profile": stored_profile}
        else:
            logger.info(f"用户 {user_id} Store 中无历史画像，进入纯 LLM 提取流程")
            return {}
    except Exception as e:
        logger.warning(f"从 Store 加载历史画像失败: {e}，回退到纯 LLM 提取")
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
# Node 1: Extract user profile from conversation
# ═══════════════════════════════════════════════════════════════════════════════

async def extract_profile_node(
    state: InsuranceAgentState,
    config: RunnableConfig | None = None,
    *,
    dependencies: AgentDependencies | None = None,
) -> dict:
    """Use LLM to extract structured profile from conversation messages."""
    messages = state.get("messages", [])
    conversation = _format_conversation(messages)

    stored_profile = state.get("stored_profile", {})
    if dependencies is not None and dependencies.tool_gateway is not None:
        result = await dependencies.tool_gateway.execute(
            "extract_customer_profile",
            {
                "conversation": conversation,
                "stored_profile_json": json.dumps(stored_profile, ensure_ascii=False),
            },
            context=ToolCallContext.from_config(config),
        )
        return {"user_profile_raw": result.data}
    if stored_profile:
        profile_raw = extract_user_profile.invoke({
            "conversation": conversation,
            "stored_profile": json.dumps(stored_profile, ensure_ascii=False),
        })
    else:
        profile_raw = extract_user_profile.invoke({"conversation": conversation})
    return {"user_profile_raw": profile_raw}


# ═══════════════════════════════════════════════════════════════════════════════
# Node 2: Validate profile — interrupt if missing required fields\
# 验证pfofile是否缺失关键信息,如果缺失,中断询问用户进行补全
# ═══════════════════════════════════════════════════════════════════════════════

async def validate_profile_node(
    state: InsuranceAgentState,
    config: RunnableConfig | None = None,
    *,
    dependencies: AgentDependencies | None = None,
) -> dict:
    """Validate extracted profile. If required fields are missing, interrupt
    and ask the user to provide them."""
    profile_raw = state.get("user_profile_raw", {})
    missing = validate_user_profile(profile_raw)

    if missing:
        missing_str = "、".join(missing)
        prompt = MISSING_FIELDS_PROMPT.format(missing_fields=missing_str)
        missing_fields = [
            field_name
            for field_name, label in REQUIRED_FIELDS.items()
            if label in missing
        ]

        # Human-in-the-loop: interrupt and wait for user input
        user_response = interrupt(
            {
                "type": "missing_profile_fields",
                "fields": missing_fields,
                "question": prompt,
            }
        )

        # Re-extract profile from the combined conversation + user response
        messages = state.get("messages", [])
        full_conversation = _format_conversation(messages) + f"\n用户补充信息: {user_response}"
        if dependencies is not None and dependencies.tool_gateway is not None:
            extraction = await dependencies.tool_gateway.execute(
                "extract_customer_profile",
                {"conversation": full_conversation, "stored_profile_json": "{}"},
                context=ToolCallContext.from_config(config),
            )
            updated_profile = extraction.data
        else:
            updated_profile = extract_user_profile.invoke({"conversation": full_conversation})

        # If still missing, interrupt again
        still_missing = validate_user_profile(updated_profile)
        if still_missing:
            still_missing_str = "、".join(still_missing)
            still_missing_fields = [
                field_name
                for field_name, label in REQUIRED_FIELDS.items()
                if label in still_missing
            ]
            user_response2 = interrupt(
                {
                    "type": "missing_profile_fields",
                    "fields": still_missing_fields,
                    "question": f"仍有以下信息缺失：{still_missing_str}。请补充：",
                }
            )
            full_conversation += f"\n用户继续补充: {user_response2}"
            if dependencies is not None and dependencies.tool_gateway is not None:
                extraction = await dependencies.tool_gateway.execute(
                    "extract_customer_profile",
                    {"conversation": full_conversation, "stored_profile_json": "{}"},
                    context=ToolCallContext.from_config(config),
                )
                updated_profile = extraction.data
            else:
                updated_profile = extract_user_profile.invoke({"conversation": full_conversation})

        profile_raw = updated_profile
        profile = UserProfile(
            age=updated_profile.get("age"),
            occupation=updated_profile.get("occupation"),
            budget=updated_profile.get("budget"),
            insurance_type=updated_profile.get("insurance_type"),
        )
    else:
        profile = UserProfile(
            age=profile_raw.get("age"),
            occupation=profile_raw.get("occupation"),
            budget=profile_raw.get("budget"),
            insurance_type=profile_raw.get("insurance_type"),
        )

    return {"user_profile": profile, "user_profile_raw": profile_raw}


# ═══════════════════════════════════════════════════════════════════════════════
# Node 3: MySQL strict query
# ═══════════════════════════════════════════════════════════════════════════════

async def query_products_node(
    state: InsuranceAgentState,
    config: RunnableConfig | None = None,
    *,
    dependencies: AgentDependencies | None = None,
) -> dict:
    """Query MySQL for products matching the user profile using strict
    condition filtering (NOT RAG similarity)."""
    profile: UserProfile = state["user_profile"]
    profile_dict = {
        "age": profile.age,
        "occupation": profile.occupation,
        "budget": profile.budget,
        "insurance_type": profile.insurance_type,
    }

    if dependencies is not None and dependencies.tool_gateway is not None:
        result = await dependencies.tool_gateway.execute(
            "search_active_insurance_products",
            profile_dict,
            context=ToolCallContext.from_config(config),
        )
        products = result.data
    else:
        products = query_insurance_products_mysql.invoke(
            {"profile_json": json.dumps(profile_dict, ensure_ascii=False)}
        )
    return {"matched_products": products}


# ═══════════════════════════════════════════════════════════════════════════════
# Node 4: RAG enrichment
# ═══════════════════════════════════════════════════════════════════════════════

async def enrich_products_node(
    state: InsuranceAgentState,
    config: RunnableConfig | None = None,
    *,
    dependencies: AgentDependencies | None = None,
) -> dict:
    """Enrich matched products with RAG context (cases, audience info, etc.).

    传入完整的产品信息和用户画像，以便 RAG 执行多路检索：
    - 产品专项查询（产品名 + 险种 + 保障/理赔）
    - 通用保险知识查询（条款/既往症/费率/FAQ）
    - 用户画像匹配查询（年龄 + 职业 + 预算 + 险种）
    """
    matched_products = state.get("matched_products", [])
    if not matched_products:
        return {"enriched_products": []}

    profile: UserProfile = state["user_profile"]
    product_ids = [p["product_id"] for p in matched_products]

    # 构建 RAG 调用参数：产品ID + 完整产品信息 + 用户画像
    invoke_args: dict[str, Any] = {
        "product_ids_json": json.dumps(product_ids, ensure_ascii=False),
        "products_json": json.dumps(matched_products, ensure_ascii=False),
    }
    if profile is not None:
        invoke_args["profile_json"] = json.dumps(
            {
                "age": profile.age,
                "occupation": profile.occupation,
                "budget": profile.budget,
                "insurance_type": profile.insurance_type,
            },
            ensure_ascii=False,
        )

    if dependencies is not None and dependencies.tool_gateway is not None:
        try:
            evidence_result = await dependencies.tool_gateway.execute(
                "retrieve_policy_evidence",
                {
                    "query": (
                        f"{profile.insurance_type} {profile.age}岁 {profile.occupation} "
                        "保障范围 理赔规则 免责条款"
                    ),
                    "product_ids": product_ids,
                    "top_k": 10,
                },
                context=ToolCallContext.from_config(config),
            )
            evidence = evidence_result.data
        except DependencyUnavailableError:
            evidence = []
        enriched = [
            {
                "product_id": product_id,
                "rag_content": "\n\n".join(
                    item["content"]
                    for item in evidence
                    if not item.get("product_id") or item.get("product_id") == product_id
                ),
            }
            for product_id in product_ids
        ]
        warnings = [] if evidence else ["条款知识库暂不可用，推荐仅依据在售产品结构化数据。"]
    else:
        enriched = rag_enrich_products.invoke(invoke_args)
    rag_map = {e["product_id"]: e["rag_content"] for e in enriched}
    for product in matched_products:
        product["rag_content"] = rag_map.get(product["product_id"], "")

    result = {"enriched_products": matched_products}
    if dependencies is not None and dependencies.tool_gateway is not None:
        result["warnings"] = warnings
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Node 5: Generate recommendation
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_recommendation_node(
    state: InsuranceAgentState,
    config: RunnableConfig | None = None,
    *,
    dependencies: AgentDependencies | None = None,
) -> dict:
    """Use LLM to generate the final recommendation with reasoning."""
    profile = state["user_profile"]
    products = state.get("enriched_products", state.get("matched_products", []))

    if not products:
        return {
            "final_recommendation": (
                "很抱歉，根据您提供的信息，暂未找到完全匹配的保险产品。\n\n"
                "建议您：\n"
                "1. 调整预算范围或保险类型后重新查询\n"
                "2. 联系我们的保险顾问获取更精准的推荐\n"
            )
        }

    profile_str = (
        f"- 年龄: {profile.age}岁\n"
        f"- 职业: {profile.occupation}\n"
        f"- 预算: {profile.budget}元/年\n"
        f"- 意向险种: {profile.insurance_type}"
    )

    products_str = _format_products(products)
    rag_context_str = _format_rag_context(products)

    if dependencies is not None and dependencies.model_gateway is not None:
        try:
            result = await dependencies.model_gateway.invoke(
                ModelRequest(
                    prompt_id="recommendation.generate",
                    variables={
                        "user_profile": profile_str,
                        "products": products_str,
                        "rag_context": rag_context_str,
                    },
                    strategy="recommend",
                ),
                context=ModelCallContext.from_config(config),
            )
            recommendation = result.data
        except Exception:
            recommendation = _fallback_recommendation(profile, products)
    else:
        recommendation = _fallback_recommendation(profile, products)

    return {"final_recommendation": recommendation}


# ═══════════════════════════════════════════════════════════════════════════════
# Node 6: 保存用户画像到 Store（跨会话记忆出口）
# ═══════════════════════════════════════════════════════════════════════════════
# 每次推荐完成后，将当前用户画像写入 PG Store
# 下次新会话时，load_profile_from_store 会自动加载

async def save_profile_to_store(
    state: InsuranceAgentState,
    config: RunnableConfig | None = None,
    *,
    store: Any = None,
    dependencies: AgentDependencies | None = None,
) -> dict:
    """将用户画像保存到 PostgreSQL Store，实现跨会话持久化。

    策略：
    - 只在画像完整时保存（4个必填字段都有值）
    - 同时保存交互摘要，方便知识回答agent了解用户背景
    - 失败不阻塞推荐流程
    """
    user_id = state.get("user_id", "")
    profile = state.get("user_profile")
    profile_raw = state.get("user_profile_raw", {})

    if not user_id or store is None or profile is None:
        return {}

    try:
        if dependencies is not None and dependencies.tool_gateway is not None:
            await dependencies.tool_gateway.execute(
                "save_profile_memory",
                {
                    "user_id": user_id,
                    "profile": {
                        "age": profile.age,
                        "occupation": profile.occupation,
                        "budget": profile.budget,
                        "insurance_type": profile.insurance_type,
                        "source": state.get("profile_source", "extracted"),
                    },
                    "interaction": {
                        "type": "recommendation",
                        "agent": "insurance_agent",
                        "profile": profile_raw,
                        "product_count": len(state.get("matched_products", [])),
                        "recommendation_preview": state.get("final_recommendation", "")[:200],
                    },
                },
                context=ToolCallContext.from_config(config),
            )
            return {}
        from shared.memory import UserMemoryStore
        memory = UserMemoryStore(store)

        # 1. 保存用户画像
        await memory.save_user_profile(user_id, {
            "age": profile.age,
            "occupation": profile.occupation,
            "budget": profile.budget,
            "insurance_type": profile.insurance_type,
            "source": state.get("profile_source", "extracted"),
        })
        logger.info(f"用户 {user_id} 画像已保存到 Store")

        # 2. 保存交互摘要（供知识回答agent了解用户背景）
        products = state.get("matched_products", [])
        await memory.save_interaction(user_id, {
            "type": "recommendation",
            "agent": "insurance_agent",
            "profile": profile_raw,
            "product_count": len(products),
            "product_ids": [p.get("product_id", "") for p in products[:5]],
            "recommendation_preview": state.get("final_recommendation", "")[:200],
        })
        logger.info(f"用户 {user_id} 交互摘要已保存")
    except Exception as e:
        logger.warning(f"保存用户画像到 Store 失败: {e}，不影响推荐结果")

    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# Conditional edges
# ═══════════════════════════════════════════════════════════════════════════════

def after_load_profile(state: InsuranceAgentState) -> Literal["validate_profile", "extract_profile"]:
    """Store 加载画像后的分支决策：
    新策略：无论 Store 是否有历史画像，始终进入 LLM 提取流程。
    Store 历史画像通过 stored_profile 字段传入 extract_profile 作为参考上下文。
    """
    return "extract_profile"


def should_query_products(state: InsuranceAgentState) -> str:
    """If profile is valid, proceed to query; otherwise end."""
    profile = state.get("user_profile")
    if profile is None:
        return END
    return "query_products"


# ═══════════════════════════════════════════════════════════════════════════════
# Build the graph（Checkpointer + Store 由应用生命周期注入）
# ═══════════════════════════════════════════════════════════════════════════════

def build_graph(*, checkpointer=None, store=None, dependencies: AgentDependencies | None = None):
    """Build and compile the insurance recommendation agent graph.

    Args:
        store: 可选的 BaseStore 实例。传入时启用跨会话记忆：
               - 新会话先查 Store 加载历史画像作为 LLM 参考上下文
               - 推荐完成后保存画像到 Store
        checkpointer: 由 FastAPI lifespan 创建的持久化 Checkpointer。

    Returns:
        编译后的 StateGraph
    """
    workflow = StateGraph(InsuranceAgentState)

    async def load_profile_node(state: InsuranceAgentState) -> dict:
        return await load_profile_from_store(state, store=store)

    async def save_profile_node(
        state: InsuranceAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        return await save_profile_to_store(
            state,
            config,
            store=store,
            dependencies=dependencies,
        )

    async def extract_profile(
        state: InsuranceAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        return await extract_profile_node(state, config, dependencies=dependencies)

    async def validate_profile(
        state: InsuranceAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        return await validate_profile_node(state, config, dependencies=dependencies)

    async def query_products(
        state: InsuranceAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        return await query_products_node(state, config, dependencies=dependencies)

    async def enrich_products(
        state: InsuranceAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        return await enrich_products_node(state, config, dependencies=dependencies)

    async def generate_recommendation(
        state: InsuranceAgentState,
        config: RunnableConfig | None = None,
    ) -> dict:
        return await generate_recommendation_node(state, config, dependencies=dependencies)

    # ── 添加节点 ──
    workflow.add_node("load_profile_from_store", load_profile_node)
    workflow.add_node("extract_profile", extract_profile)
    workflow.add_node("validate_profile", validate_profile)
    workflow.add_node("query_products", query_products)
    workflow.add_node("enrich_products", enrich_products)
    workflow.add_node("generate_recommendation", generate_recommendation)
    workflow.add_node("save_profile_to_store", save_profile_node)

    # ── 入口 ──
    workflow.set_entry_point("load_profile_from_store")

    # ── 边 ──
    # Store加载 → 新策略：无论是否加载到历史画像，都走 LLM 提取流程
    workflow.add_conditional_edges(
        "load_profile_from_store",
        after_load_profile,
        {"validate_profile": "validate_profile", "extract_profile": "extract_profile"},
    )
    workflow.add_edge("extract_profile", "validate_profile")
    workflow.add_conditional_edges(
        "validate_profile",
        should_query_products,
        {"query_products": "query_products", END: END},
    )
    workflow.add_edge("query_products", "enrich_products")
    workflow.add_edge("enrich_products", "generate_recommendation")
    workflow.add_edge("generate_recommendation", "save_profile_to_store")  # [NEW]
    workflow.add_edge("save_profile_to_store", END)

    return workflow.compile(checkpointer=checkpointer, store=store)


# langgraph.json 的无持久化定义；正式 HTTP 入口由 lifespan 注入 PostgreSQL。
graph = build_graph()



# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _format_conversation(messages: list) -> str:
    """将消息列表格式化为对话文本，兼容 LangChain 对象和普通 dict。

    消息可能是：
    - LangChain BaseMessage 对象（有 type/content 属性）
    - 普通 dict（有 role/content 键，如 {"role": "user", "content": "..."}）
    """
    if not messages:
        return ""
    lines = []
    for msg in messages:
        # 兼容 dict 和对象两种格式
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

        role_label = "用户" if role in ("human", "user") else "助手"
        lines.append(f"{role_label}: {content}")
    return "\n".join(lines)


def _format_products(products: list[dict]) -> str:
    lines = []
    for i, p in enumerate(products, 1):
        lines.append(
            f"{i}. [{p['product_id']}] {p['product_name']}\n"
            f"   - 险种: {p['insurance_type']}\n"
            f"   - 投保年龄: {p['min_age']}-{p['max_age']}岁\n"
            f"   - 保费范围: {p['min_price']}-{p['max_price']}元/年\n"
            f"   - 适合职业: {p['target_occupations']}\n"
            f"   - 产品描述: {p['description']}"
        )
    return "\n".join(lines)


def _format_rag_context(products: list[dict]) -> str:
    parts = []
    for p in products:
        rag = p.get("rag_content", "")
        if rag:
            parts.append(f"### {p['product_name']}\n{rag}")
    return "\n\n".join(parts) if parts else "暂无补充资料"


def _fallback_recommendation(profile: UserProfile, products: list[dict]) -> str:
    if not products:
        return "暂未找到匹配的保险产品，请调整条件后重试。"

    lines = [
        "## 📋 保险产品推荐",
        "",
        f"根据您的需求（{profile.age}岁，{profile.occupation}，预算{profile.budget}元/年，意向{profile.insurance_type}），",
        f"为您找到以下{len(products)}款产品：",
        "",
    ]

    for i, p in enumerate(products, 1):
        lines.append(f"### {i}. {p['product_name']}")
        lines.append(f"- **产品编号**: {p['product_id']}")
        lines.append(f"- **保费**: {p['min_price']}-{p['max_price']}元/年")
        lines.append(f"- **产品描述**: {p['description']}")
        if p.get("rag_content"):
            lines.append(f"- **相关资料**: {p['rag_content'][:200]}...")
        lines.append("")

    lines.append("---")
    lines.append("> 以上推荐基于您提供的信息，具体保费以实际核保为准。如有疑问请联系保险顾问。")
    return "\n".join(lines)
