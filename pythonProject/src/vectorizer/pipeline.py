"""向量化流水线 — 编排 scan -> load -> chunk -> embed -> write 全过程。"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _create_embedding_function(config: "VectorizerConfig") -> callable:
    """创建文本嵌入函数。

    优先使用 DashScope SDK 原生路径（最稳定）：
        pip install dashscope

    如果 dashscope 未安装，自动降级到 langchain OpenAIEmbeddings + DashScope 兼容接口：
        pip install langchain-openai
    """
    # 策略 1：DashScope SDK 原生路径
    try:
        from dashscope import TextEmbedding as DashTextEmbedding

        def embed_texts(texts: list[str]) -> list[list[float]]:
            resp = DashTextEmbedding.call(
                model=config.embedding_model,
                input=texts,
                dimension=config.embedding_dim,
                api_key=config.dashscope_api_key,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"DashScope embedding API 返回异常: {resp.status_code} - {resp.message}"
                )
            return [e["embedding"] for e in resp.output["embeddings"]]

        return embed_texts
    except ImportError:
        pass

    # 策略 2：降级到 OpenAI 兼容接口（langchain-openai + DashScope 兼容端点）
    try:
        from langchain_openai import OpenAIEmbeddings
    except ImportError:
        logger.error(
            "未安装任何嵌入后端。请执行: pip install dashscope\n"
            "  或: pip install langchain-openai"
        )
        sys.exit(1)

    emb = OpenAIEmbeddings(
        model=config.embedding_model,
        api_key=config.dashscope_api_key,
        base_url=os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
    )

    def embed_texts(texts: list[str]) -> list[list[float]]:
        return emb.embed_documents(texts)

    return embed_texts


def run_pipeline(config: "VectorizerConfig | None" = None) -> int:
    """执行完整向量化流水线。

    Args:
        config: 向量化配置，为 None 时使用环境变量默认值。

    Returns:
        写入 Milvus 的 chunk 总数。
    """
    if config is None:
        from vectorizer.config import VectorizerConfig
        config = VectorizerConfig()

    start_time = time.time()
    logger.info("=" * 50)
    logger.info("向量化流水线启动")
    logger.info("扫描目录: %s", config.scan_root_dir)
    logger.info("Milvus Collection: %s", config.milvus_collection)
    logger.info("分块参数: size=%d, overlap=%d", config.chunk_size, config.chunk_overlap)
    logger.info("=" * 50)

    # Step 1: 扫描文件
    from vectorizer.loader import scan_files, load_file
    from vectorizer.chunker import chunk_document
    from vectorizer.writer import MilvusWriter

    file_paths = scan_files(config)
    if not file_paths:
        logger.warning("未找到可向量化的文件")
        return 0

    # Step 2: 加载 -> 分块
    all_chunks: list = []
    for fpath in file_paths:
        doc = load_file(fpath)
        if doc is None:
            continue
        chunks = chunk_document(doc, config)
        all_chunks.extend(chunks)
        logger.info("  %s -> %d chunks", doc["path"], len(chunks))

    if not all_chunks:
        logger.warning("所有文件加载后未产生任何文本块")
        return 0

    logger.info("共产生 %d 个文本块，来自 %d 个文件", len(all_chunks), len(file_paths))

    # Step 3: 嵌入函数
    embed_func = _create_embedding_function(config)

    # Step 4: 连接 Milvus 并写入
    writer = MilvusWriter(config)
    try:
        writer.connect()
        writer.create_collection(recreate=config.recreate_collection)
        written = writer.write_chunks(all_chunks, embed_func, batch_size=config.batch_size)
    except Exception as e:
        logger.error("Milvus 写入过程异常: %s", e)
        written = 0
    finally:
        writer.disconnect()

    elapsed = time.time() - start_time
    logger.info("=" * 50)
    logger.info("流水线完成 | 写入 %d chunks | 耗时 %.1f 秒", written, elapsed)
    logger.info("=" * 50)
    return written


def main() -> None:
    """CLI 入口。"""
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="将本地文件向量化并写入 Milvus 向量库",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dir", default=os.getenv("SCAN_ROOT_DIR", "."),
        help="要扫描的根目录",
    )
    parser.add_argument(
        "--collection", default=os.getenv("MILVUS_COLLECTION", "file_documents"),
        help="Milvus Collection 名称",
    )
    parser.add_argument(
        "--host", default=os.getenv("MILVUS_HOST", "localhost"),
        help="Milvus 主机",
    )
    parser.add_argument(
        "--port", default=os.getenv("MILVUS_PORT", "19530"),
        help="Milvus 端口",
    )
    parser.add_argument(
        "--uri", default=os.getenv("MILVUS_URI", ""),
        help="Milvus URI（Zilliz Cloud 场景，优先级高于 host:port）",
    )
    parser.add_argument(
        "--token", default=os.getenv("MILVUS_TOKEN", ""),
        help="Milvus Token（Zilliz Cloud 场景）",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=int(os.getenv("CHUNK_SIZE", "1024")),
        help="分块大小（字符数）",
    )
    parser.add_argument(
        "--chunk-overlap", type=int, default=int(os.getenv("CHUNK_OVERLAP", "200")),
        help="分块重叠（字符数）",
    )
    parser.add_argument(
        "--batch-size", type=int, default=int(os.getenv("BATCH_SIZE", "100")),
        help="每批写入的 Chunk 数量",
    )
    parser.add_argument(
        "--max-files", type=int, default=int(os.getenv("MAX_FILES", "0")),
        help="最多处理文件数（0 = 不限）",
    )
    parser.add_argument(
        "--recreate", action="store_true",
        default=os.getenv("RECREATE_COLLECTION", "false").lower() == "true",
        help="重建 Collection（删除已有数据）",
    )
    parser.add_argument(
        "--embedding-model", default=os.getenv("EMBEDDING_MODEL", "text-embedding-v3"),
        help="Embedding 模型名称",
    )
    parser.add_argument(
        "--embedding-dim", type=int, default=int(os.getenv("EMBEDDING_DIM", "1024")),
        help="Embedding 向量维度",
    )

    args = parser.parse_args()

    from vectorizer.config import VectorizerConfig

    config = VectorizerConfig(
        scan_root_dir=args.dir,
        milvus_collection=args.collection,
        milvus_host=args.host,
        milvus_port=args.port,
        milvus_uri=args.uri,
        milvus_token=args.token,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        batch_size=args.batch_size,
        max_files=args.max_files,
        recreate_collection=args.recreate,
        embedding_model=args.embedding_model,
        embedding_dim=args.embedding_dim,
    )

    run_pipeline(config)


if __name__ == "__main__":
    main()
