"""
共享 Milvus 工具 — 嵌入函数 + 连接 + 向量检索

供 insurance_agent 和 knowledge_agent 共用。
与 vectorizer/pipeline.py 使用相同的 Milvus 连接和 Embedding 模型。
"""
from __future__ import annotations

import os
from typing import Any

# ── 配置（环境变量，与 vectorizer/config.py 同名） ──
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
MILVUS_URI = os.getenv("MILVUS_URI", "")
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN", "")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "file_documents")
MILVUS_USER = os.getenv("MILVUS_USER", "")
MILVUS_PASSWORD = os.getenv("MILVUS_PASSWORD", "")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# ── 模块级缓存 ──
_embed_func: Any = None
_milvus_available: bool | None = None


def is_milvus_available() -> bool:
    """检测 Milvus + Embedding 是否可用。"""
    global _milvus_available
    if _milvus_available is not None:
        return _milvus_available
    if not DASHSCOPE_API_KEY:
        _milvus_available = False
        return False
    try:
        import pymilvus  # noqa: F401
        _milvus_available = True
        return True
    except ImportError:
        _milvus_available = False
        return False


def get_embedding_function() -> callable | None:
    """创建文本嵌入函数（单例缓存）。

    优先 DashScope SDK 原生路径，降级到 langchain_openai 兼容路径。
    """
    global _embed_func
    if _embed_func is not None:
        return _embed_func
    if not DASHSCOPE_API_KEY:
        return None

    # 策略 1：DashScope SDK 原生路径
    try:
        from dashscope import TextEmbedding as DashTextEmbedding

        def embed_texts(texts: list[str]) -> list[list[float]]:
            resp = DashTextEmbedding.call(
                model=EMBEDDING_MODEL,
                input=texts,
                dimension=EMBEDDING_DIM,
                api_key=DASHSCOPE_API_KEY,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"DashScope embedding API 异常: {resp.status_code} - {resp.message}"
                )
            return [e["embedding"] for e in resp.output["embeddings"]]

        _embed_func = embed_texts
        return _embed_func
    except ImportError:
        pass

    # 策略 2：降级到 OpenAI 兼容接口
    try:
        from langchain_openai import OpenAIEmbeddings
    except ImportError:
        return None

    emb = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=DASHSCOPE_API_KEY,
        base_url=DASHSCOPE_BASE_URL,
    )

    def embed_texts(texts: list[str]) -> list[list[float]]:
        return emb.embed_documents(texts)

    _embed_func = embed_texts
    return _embed_func


def get_milvus_collection(collection_name: str | None = None) -> Any | None:
    """连接 Milvus 并返回已加载的 Collection 对象。

    Args:
        collection_name: 集合名，默认使用 MILVUS_COLLECTION 环境变量。
    """
    if not is_milvus_available():
        return None

    coll_name = collection_name or MILVUS_COLLECTION

    try:
        from pymilvus import Collection, connections, utility
    except ImportError:
        return None

    try:
        if MILVUS_URI:
            connections.connect(
                alias="shared_milvus",
                uri=MILVUS_URI,
                token=MILVUS_TOKEN,
            )
        else:
            connections.connect(
                alias="shared_milvus",
                host=MILVUS_HOST,
                port=MILVUS_PORT,
                user=MILVUS_USER or None,
                password=MILVUS_PASSWORD or None,
            )

        if not utility.has_collection(coll_name, using="shared_milvus"):
            return None

        collection = Collection(coll_name, using="shared_milvus")
        collection.load()
        return collection
    except Exception:
        return None


def milvus_search(
    query_text: str,
    top_k: int = 5,
    collection_name: str | None = None,
) -> list[dict]:
    """对 Milvus 执行向量检索。

    Args:
        query_text: 查询文本。
        top_k: 返回的 chunk 数。
        collection_name: 集合名，默认 MILVUS_COLLECTION。

    Returns:
        命中列表，每项含 text, score, file_path, file_type, metadata。
    """
    collection = get_milvus_collection(collection_name)
    embed_func = get_embedding_function()
    if collection is None or embed_func is None:
        return []

    try:
        vectors = embed_func([query_text])
        results = collection.search(
            data=[vectors[0]],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=top_k,
            output_fields=["text", "file_path", "file_type", "metadata"],
        )

        hits = []
        for hit in results[0]:
            hits.append({
                "id": hit.id,
                "score": hit.score,
                "text": hit.entity.get("text", ""),
                "file_path": hit.entity.get("file_path", ""),
                "file_type": hit.entity.get("file_type", ""),
                "metadata": hit.entity.get("metadata", {}),
            })
        return hits
    except Exception:
        return []
