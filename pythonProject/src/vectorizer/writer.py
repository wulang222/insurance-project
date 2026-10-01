"""Milvus 写入器 — 创建 Collection、批量嵌入并写入向量数据。"""

from __future__ import annotations

import json
import logging

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from vectorizer.config import VectorizerConfig
from vectorizer.chunker import Chunk

logger = logging.getLogger(__name__)


class MilvusWriter:
    """封装 Milvus 连接、Collection 管理、批量写入操作。"""

    def __init__(self, config: VectorizerConfig):
        self.config = config
        self.collection_name = config.milvus_collection
        self.dim = config.embedding_dim
        self._collection: Collection | None = None

    # ── 连接管理 ──

    def connect(self) -> None:
        """建立与 Milvus 的连接。"""
        args = self.config.milvus_connection_args()
        if "uri" in args:
            connections.connect(uri=args["uri"], token=args.get("token", ""))
            logger.info("已连接到 Milvus (URI): %s", args["uri"])
        else:
            connections.connect(
                host=args["host"],
                port=args["port"],
                user=args.get("user"),
                password=args.get("password"),
            )
            logger.info("已连接到 Milvus: %s:%s", args["host"], args["port"])

    def disconnect(self) -> None:
        connections.disconnect("default")
        logger.info("已断开 Milvus 连接")

    # ── Collection 管理 ──

    def _build_schema(self) -> CollectionSchema:
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
            FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="file_type", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="metadata", dtype=DataType.JSON),
        ]
        return CollectionSchema(fields, description="向量化文档文件")

    def create_collection(self, recreate: bool = False) -> Collection:
        """创建或重建 Collection，自动创建 IVF_FLAT 索引。"""
        if recreate and utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
            logger.info("已删除已有 Collection: %s", self.collection_name)

        if utility.has_collection(self.collection_name):
            collection = Collection(self.collection_name)
            collection.load()
            logger.info(
                "Collection 已存在: %s (rows=%d)",
                self.collection_name,
                collection.num_entities,
            )
        else:
            schema = self._build_schema()
            collection = Collection(
                name=self.collection_name,
                schema=schema,
                using="default",
            )
            logger.info("Collection 已创建: %s", self.collection_name)

        # 创建索引（IVF_FLAT 是通用默认，后续可按需调参）
        collection.create_index(
            field_name="embedding",
            index_params={
                "metric_type": "IP",  # 内积，配合归一化等价于余弦相似度
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            },
        )
        collection.load()
        self._collection = collection
        return collection

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._collection = Collection(self.collection_name)
            self._collection.load()
        return self._collection

    # ── 写入 ──

    def write_chunks(
        self,
        chunks: list[Chunk],
        embed_func: callable,
        batch_size: int = 100,
    ) -> int:
        """批量嵌入并写入 Milvus。

        Args:
            chunks: 待写入的文本块列表。
            embed_func: 接受字符串列表、返回向量列表的函数。
            batch_size: 每批写入的 chunk 数量。

        Returns:
            成功写入的 Chunk 数量。
        """
        if not chunks:
            return 0

        total = 0
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            texts = [c.text for c in batch]

            # 嵌入
            try:
                embeddings = embed_func(texts)
            except Exception as e:
                logger.error("嵌入生成失败 (batch %d): %s", start // batch_size, e)
                continue

            # 方案一：严格按照 Schema 的顺序组装数据
            try:
                self.collection.insert(
                    [
                        [c.text for c in batch],  # 1. text
                        embeddings,  # 2. embedding
                        [c.file_path for c in batch],  # 3. file_path
                        [c.file_type for c in batch],  # 4. file_type
                        [c.chunk_index for c in batch],  # 5. chunk_index
                        [
                            json.dumps(c.metadata, ensure_ascii=False) for c in batch
                        ],  # 6. metadata
                    ]
                )
                total += len(batch)
                logger.info(
                    "已写入 batch %d/%d (%d chunks)",
                    start // batch_size + 1,
                    (len(chunks) - 1) // batch_size + 1,
                    len(batch),
                )
            except Exception as e:
                logger.error("Milvus 写入失败 (batch %d): %s", start // batch_size, e)
                continue

        self.collection.flush()
        logger.info("写入完成，共 %d 个 chunk 写入 %s", total, self.collection_name)
        return total

    # ── 查询（供后续集成 RAG 时使用）──

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        expr: str | None = None,
    ) -> list[dict]:
        """向量检索，返回最近似的 top_k 条记录。"""
        self.collection.load()
        results = self.collection.search(
            data=[query_vector],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=top_k,
            expr=expr,
            output_fields=["text", "file_path", "file_type", "chunk_index", "metadata"],
        )
        hits = []
        for hit in results[0]:
            hits.append(
                {
                    "id": hit.id,
                    "score": hit.score,
                    "text": hit.entity.get("text"),
                    "file_path": hit.entity.get("file_path"),
                    "file_type": hit.entity.get("file_type"),
                    "chunk_index": hit.entity.get("chunk_index"),
                    "metadata": hit.entity.get("metadata"),
                }
            )
        return hits
