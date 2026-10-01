"""
共享内存模块 — PostgreSQL 持久化的 Store 和 Checkpointer

提供两个核心能力：
1. State Checkpointer（会话状态）: 每个会话的 LangGraph 状态持久化到 PG
2. Store（跨会话记忆）: 用户画像、偏好、交互历史跨会话持久化

设计理念：
┌─────────────────────────────────────────────────────┐
│                   PostgreSQL                        │
│  ┌──────────────────┐  ┌──────────────────────────┐│
│  │ checkpoint 表     │  │ store 表                  ││
│  │ (会话级状态)       │  │ (跨会话用户记忆)           ││
│  │ - thread_id       │  │ namespace: users/{uid}/.. ││
│  │ - checkpoint      │  │ - profile: 用户画像        ││
│  │ - metadata        │  │ - preferences: 偏好       ││
│  │ - pending_sends   │  │ - interactions: 交互摘要   ││
│  └──────────────────┘  └──────────────────────────┘│
└─────────────────────────────────────────────────────┘

使用场景：
- 用户在会话A中告诉agent自己28岁/程序员/预算5000
- 用户新开会话B → agent自动从Store加载已有画像，无需重复询问
- 知识回答agent加载用户画像，更精准地理解问题上下文
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.store.base import BaseStore


# ═══════════════════════════════════════════════════════════════════════════════
# PostgreSQL 连接配置
# ═══════════════════════════════════════════════════════════════════════════════
# 通过环境变量配置，与 MySQL 配置区分开

PG_CONN_STRING = os.getenv(
    "POSTGRES_URI",
    "postgresql://postgres:postgres@localhost:5432/insurance_agent",
)
PG_PIPELINE = os.getenv("PG_PIPELINE", "false").lower() == "true"


# ═══════════════════════════════════════════════════════════════════════════════
# Checkpointer & Store 工厂函数
# ═══════════════════════════════════════════════════════════════════════════════
# 使用 async context manager 保证连接正确释放

@asynccontextmanager
async def get_pg_checkpointer():
    """创建 PostgreSQL Checkpointer 的异步上下文管理器

    用于 LangGraph 的 compile(checkpointer=...)，将每个会话的
    状态（messages, extracted_profile 等）持久化到 PG。

    使用方式：
        async with get_pg_checkpointer() as checkpointer:
            graph = workflow.compile(checkpointer=checkpointer)
    """
    async with AsyncPostgresSaver.from_conn_string(
        PG_CONN_STRING,
        pipeline=PG_PIPELINE,
    ) as checkpointer:
        await checkpointer.setup()
        yield checkpointer


@asynccontextmanager
async def get_pg_store():
    """创建 PostgreSQL Store 的异步上下文管理器

    Store 用于跨会话的长期记忆：用户画像、偏好、交互历史等。
    与 Checkpointer 不同，Store 的数据不随会话结束而清除。

    Store 的命名空间设计：
        ("users", "{user_id}", "profile")       → 用户画像
        ("users", "{user_id}", "preferences")   → 用户偏好
        ("users", "{user_id}", "interactions")  → 交互摘要

    使用方式：
        async with get_pg_store() as store:
            await store.aput(("users", "u1", "profile"), "main", {...})
    """
    async with AsyncPostgresStore.from_conn_string(
        PG_CONN_STRING,
        pipeline=PG_PIPELINE,
    ) as store:
        await store.setup()
        yield store


# ═══════════════════════════════════════════════════════════════════════════════
# 用户记忆管理器（高层封装）
# ═══════════════════════════════════════════════════════════════════════════════
# 封装 Store 的读写操作，提供语义化的 API
# 两个 agent 都通过此类读写用户记忆，避免直接操作底层 Store

class UserMemoryStore:
    """跨会话用户记忆管理器

    封装了 PG Store 的 CRUD 操作，提供以下能力：
    1. 存储/加载用户画像 → 新会话无需重复询问
    2. 存储/加载用户偏好 → 更精准的推荐
    3. 记录交互摘要 → 为后续分析提供数据基础
    """

    # ── 命名空间常量 ──
    NS_PROFILE = "profile"        # 用户画像
    NS_PREFERENCES = "preferences"  # 用户偏好
    NS_INTERACTIONS = "interactions"  # 交互摘要

    def __init__(self, store: BaseStore):
        """传入已初始化的 PG Store 实例"""
        self._store = store

    # ── 用户画像 ────────────────────────────────────────

    async def save_user_profile(self, user_id: str, profile: dict) -> None:
        """保存或更新用户画像（upsert）

        存储结构：
        {
            "age": 28,
            "occupation": "程序员",
            "budget": 5000,
            "insurance_type": "重疾险",
            "updated_at": "2026-06-10T12:00:00Z",
            "source": "extracted" | "manual"
        }
        """
        profile["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self._store.aput(
            self._ns(user_id, self.NS_PROFILE),
            "main",  # key: 当前只有一个profile版本，用"main"标识
            profile,
        )

    async def load_user_profile(self, user_id: str) -> dict | None:
        """加载用户画像

        Returns:
            用户画像 dict；如果从未存储过返回 None
        """
        item = await self._store.aget(
            self._ns(user_id, self.NS_PROFILE),
            "main",
        )
        if item is None:
            return None
        return item.value if hasattr(item, "value") else item.get("value")

    async def has_user_profile(self, user_id: str) -> bool:
        """检查用户是否已有画像（用于判断是否需要提取）"""
        profile = await self.load_user_profile(user_id)
        return profile is not None

    # ── 用户偏好 ────────────────────────────────────────

    async def save_user_preferences(self, user_id: str, preferences: dict) -> None:
        """保存用户偏好（如常用险种、关注的产品等）

        存储结构：
        {
            "favorite_insurance_types": ["重疾险", "医疗险"],
            "favorite_products": ["CI001", "MI001"],
            "price_sensitivity": "medium",  # low/medium/high
            "updated_at": "..."
        }
        """
        preferences["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self._store.aput(
            self._ns(user_id, self.NS_PREFERENCES),
            "main",
            preferences,
        )

    async def load_user_preferences(self, user_id: str) -> dict | None:
        """加载用户偏好"""
        item = await self._store.aget(
            self._ns(user_id, self.NS_PREFERENCES),
            "main",
        )
        if item is None:
            return None
        return item.value if hasattr(item, "value") else item.get("value")

    # ── 交互历史 ────────────────────────────────────────

    async def save_interaction(self, user_id: str, interaction: dict) -> None:
        """保存一次交互摘要

        存储结构：
        {
            "timestamp": "2026-06-10T12:00:00Z",
            "agent": "insurance_agent" | "knowledge_agent",
            "question_summary": "...",
            "intent": "recommend" | "qa",
            "result_summary": "...",
            "satisfaction": null | "positive" | "negative"
        }

        每条交互用时间戳作为 key，支持多版本存储
        """
        key = f"interaction_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        interaction["timestamp"] = datetime.now(timezone.utc).isoformat()
        await self._store.aput(
            self._ns(user_id, self.NS_INTERACTIONS),
            key,
            interaction,
        )

    async def search_interactions(
        self, user_id: str, query: str = "", limit: int = 10
    ) -> list[dict]:
        """搜索用户历史交互

        使用 PG Store 内置的语义搜索能力（基于 embedding）
        """
        items = await self._store.asearch(
            self._ns(user_id, self.NS_INTERACTIONS),
            query=query,
            limit=limit,
        )
        return [item.value if hasattr(item, "value") else item.get("value", {}) for item in items]

    async def get_recent_interactions(self, user_id: str, limit: int = 5) -> list[dict]:
        """获取最近的交互摘要（用于问题重写时的上下文）"""
        items = await self._store.asearch(
            self._ns(user_id, self.NS_INTERACTIONS),
            limit=limit,
        )
        return [item.value if hasattr(item, "value") else item.get("value", {}) for item in items]

    # ── 综合上下文（供 agent 使用） ──────────────────────

    async def load_user_context(self, user_id: str) -> dict:
        """加载用户的完整上下文（画像 + 偏好 + 近期交互）

        这个方法是 agent 在使用 Store 时的统一入口
        返回一个综合 dict，包含所有可用信息
        """
        profile = await self.load_user_profile(user_id)
        preferences = await self.load_user_preferences(user_id)
        recent = await self.get_recent_interactions(user_id, limit=3)
        return {
            "user_id": user_id,
            "profile": profile,
            "preferences": preferences,
            "recent_interactions": recent,
            "is_new_user": profile is None,
        }

    # ── 辅助方法 ────────────────────────────────────────

    @staticmethod
    def _ns(user_id: str, category: str) -> tuple[str, ...]:
        """构建 Store 命名空间

        层级结构: ("users", "{user_id}", "{category}")
        例如: ("users", "user_123", "profile")
        """
        return ("users", user_id, category)
