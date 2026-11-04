"""
知识回答Agent — 配置

复用 insurance_agent 中已有的 LLM 工厂函数（通义千问 DashScope），
此处只追加知识回答Agent特有的配置项。
"""

from __future__ import annotations

import os

# 直接复用通义千问的 LLM 工厂，避免重复配置


# ── RAG 多集合配置 ──────────────────────────────────────────
# 课题二中定义了多层架构，这里用多个 Chroma collection 模拟：
#   - insurance_terms     : 条款解释（等待期、免责、保障范围等）
#   - insurance_claims    : 理赔规则与案例
#   - insurance_faq       : 常见问题
RAG_COLLECTIONS = {
    "terms": os.getenv("RAG_COLLECTION_TERMS", "insurance_terms"),
    "claims": os.getenv("RAG_COLLECTION_CLAIMS", "insurance_claims"),
    "faq": os.getenv("RAG_COLLECTION_FAQ", "insurance_faq"),
}

# Chroma 本地持久化目录
CHROMA_PERSIST_DIR = os.getenv("VECTOR_PERSIST_DIR", "./chroma_data")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")

# RAG 检索参数
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))  # 每个 collection 检索数量

# ── 数据库可查询的字段映射 ──────────────────────────────────
# 当意图识别为 "db" 时，告诉 LLM 它可以查询这些字段
DB_QUERYABLE_FIELDS = [
    ("product_name", "产品名称"),
    ("insurance_type", "险种类型"),
    ("min_age", "最小投保年龄"),
    ("max_age", "最大投保年龄"),
    ("min_price", "最低保费"),
    ("max_price", "最高保费"),
    ("target_occupations", "适合职业"),
    ("description", "产品描述"),
]
