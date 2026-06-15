"""文件向量化模块 — 将本地文档加载、分割、嵌入并写入 Milvus 向量库。"""

from vectorizer.pipeline import run_pipeline
from vectorizer.config import VectorizerConfig

__all__ = ["run_pipeline", "VectorizerConfig"]
