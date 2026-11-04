"""Configuration for the insurance recommendation agent."""

from __future__ import annotations

import os
from typing import Any

# LLM model — 通义千问 via DashScope
DEFAULT_MODEL = os.getenv("INSURANCE_AGENT_MODEL", "qwen3.7-plus")

# DashScope API
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# 通用 LLM 参数
LLM_TEMPERATURE = 0.7
LLM_EXTRA_BODY: dict[str, Any] = {"thinking": {"type": "disabled"}}

# MySQL connection（用于产品数据查询）
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "insurance"),
}

# PostgreSQL connection（用于 Store 跨会话记忆 + Checkpoint 状态持久化）
POSTGRES_URI = os.getenv(
    "POSTGRES_URI",
    "postgresql://postgres:postgres@localhost:5432/insurance_agent",
)

# Milvus RAG 检索配置（与 vectorizer 共用同一向量库）
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
MILVUS_URI = os.getenv("MILVUS_URI", "")       # Zilliz Cloud 场景，优先级高于 host:port
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN", "")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "file_documents")
MILVUS_USER = os.getenv("MILVUS_USER", "")
MILVUS_PASSWORD = os.getenv("MILVUS_PASSWORD", "")

# Embedding 模型配置（通义千问 text-embedding-v3，与 vectorizer 保持一致）
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# RAG 检索参数
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))         # 每条查询返回的 chunk 数
RAG_QUERY_COUNT = int(os.getenv("RAG_QUERY_COUNT", "3"))  # 每个产品的查询数（多策略检索）


def create_llm(temperature: float | None = None) -> Any:
    """Create a ChatOpenAI instance configured for DashScope (通义千问)."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=DEFAULT_MODEL,
        api_key=DASHSCOPE_API_KEY,
        base_url=DASHSCOPE_BASE_URL,
        temperature=temperature if temperature is not None else LLM_TEMPERATURE,
        extra_body=LLM_EXTRA_BODY,
    )
