"""文本分块 — 按语意段落递归切分，保留文件元数据。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from vectorizer.config import VectorizerConfig


@dataclass
class Chunk:
    """单个文本块，保留完整的溯源信息。"""
    text: str
    file_path: str
    file_type: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_document(
    doc: dict[str, Any],
    config: VectorizerConfig,
) -> list[Chunk]:
    """将单个加载后的文档按配置切分成多个 Chunk。

    Args:
        doc: loader.load_file() 返回的文档字典。
        config: 分块参数来自 VectorizerConfig。

    Returns:
        Chunk 列表，每个携带文件溯源元数据。
    """
    content = doc["content"]
    if not content or not content.strip():
        return []

    # 按文件类型选择分隔符优先级
    file_type = doc.get("file_type", "")
    if file_type in ("py", "java", "kt", "js", "ts", "jsx", "tsx", "css"):
        separators = [
            "\n\n", "\n", " ", "",
        ]
    elif file_type in ("xml", "html"):
        separators = [
            "\n\n", "\n", " ", "",
        ]
    else:
        separators = [
            "\n\n", "\n", "。", "；", "，", " ", "",
        ]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=separators,
        length_function=len,
        add_start_index=True,
    )

    texts = splitter.split_text(content)

    chunks: list[Chunk] = []
    base_meta = doc.get("metadata", {})
    for idx, text in enumerate(texts):
        chunks.append(
            Chunk(
                text=text,
                file_path=doc["path"],
                file_type=doc["file_type"],
                chunk_index=idx,
                metadata={**base_meta, "chunk_count": len(texts)},
            )
        )
    return chunks
