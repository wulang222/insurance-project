"""向量化任务配置 — Milvus 连接、Embedding、文件扫描、分块参数。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VectorizerConfig:
    """向量化全流程配置，优先从环境变量读取，支持代码层面覆盖。"""

    # ── Milvus 连接 ──
    milvus_host: str = field(default_factory=lambda: os.getenv("MILVUS_HOST", "localhost"))
    milvus_port: str = field(default_factory=lambda: os.getenv("MILVUS_PORT", "19530"))
    # Zilliz Cloud 场景：设 MILVUS_URI 和 MILVUS_TOKEN，优先级高于 host:port
    milvus_uri: str = field(default_factory=lambda: os.getenv("MILVUS_URI", ""))
    milvus_token: str = field(default_factory=lambda: os.getenv("MILVUS_TOKEN", ""))
    milvus_collection: str = field(
        default_factory=lambda: os.getenv("MILVUS_COLLECTION", "file_documents")
    )
    milvus_user: str = field(default_factory=lambda: os.getenv("MILVUS_USER", ""))
    milvus_password: str = field(default_factory=lambda: os.getenv("MILVUS_PASSWORD", ""))

    # ── Embedding（DashScope 通义千问向量化模型） ──
    # 模型: text-embedding-v3（默认 1024 维）, text-embedding-v2
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
    )
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "1024"))
    dashscope_api_key: str = field(
        default_factory=lambda: os.getenv("DASHSCOPE_API_KEY", "")
    )
    

    # ── 文件扫描 ──
    scan_root_dir: str = field(default_factory=lambda: os.getenv("SCAN_ROOT_DIR", "."))
    include_extensions: tuple[str, ...] = (
        ".md", ".txt", ".rst",
        ".pdf",
        ".docx", ".doc",
        ".xlsx", ".xls", ".csv",
        ".py", ".java", ".kt", ".kts",
        ".xml", ".yaml", ".yml", ".json", ".toml",
        ".html", ".css", ".js", ".ts", ".jsx", ".tsx",
        ".sql", ".properties",
    )
    exclude_dirs: tuple[str, ...] = (
        ".git", ".idea", ".tools", ".workflow", ".ruff_cache",
        "__pycache__", "node_modules", "target", "build", "dist",
        ".venv", "venv", ".egg-info",
    )
    exclude_files: tuple[str, ...] = (
        "*.lock", "package-lock.json", "yarn.lock",
        "*.pyc", "*.pyo", "*.so", "*.dll", "*.exe",
    )

    # ── 分块参数 ──
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1024"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "200"))

    # ── 执行控制 ──
    batch_size: int = int(os.getenv("BATCH_SIZE", "100"))
    max_files: int = int(os.getenv("MAX_FILES", "0"))  # 0 = 不限
    recreate_collection: bool = os.getenv("RECREATE_COLLECTION", "false").lower() == "true"

    def milvus_connection_args(self) -> dict[str, Any]:
        """返回 pymilvus.connect 可用的连接参数字典。"""
        if self.milvus_uri:
            return {"uri": self.milvus_uri, "token": self.milvus_token}
        return {
            "host": self.milvus_host,
            "port": self.milvus_port,
            "user": self.milvus_user or None,
            "password": self.milvus_password or None,
        }

    def embedding_kwargs(self) -> dict[str, Any]:
        """返回适合 DashScope 的嵌入参数字典。"""
        return {
            "api_key": self.dashscope_api_key,
            "model": self.embedding_model,
            "dimension": self.embedding_dim,
        }
