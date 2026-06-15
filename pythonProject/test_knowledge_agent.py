"""
知识问答 Agent — 本地测试（加载 .env，走真实服务 + PG Store 持久化）

流程: load_user_context → query_rewrite → intent_recognition → db_query/rag_search → generate_answer

用法:
    cd pythonProject
    python test_knowledge_agent.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

# ── 0. 环境准备 ──
from dotenv import load_dotenv
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)
print(f"✅ 已加载 .env: {_env_path}")

sys.path.insert(0, str(Path(__file__).parent / "src"))

from shared.memory import get_pg_store, UserMemoryStore, PG_CONN_STRING


def print_line(char: str = "─", width: int = 64) -> None:
    print(char * width)


def print_header(title: str) -> None:
    print()
    print_line("═")
    print(f"  {title}")
    print_line("═")


async def run_one(graph, question: str, user_id: str, label: str) -> dict:
    print_header(label)
    print(f"\n  💬 用户: {question}")

    config = {"configurable": {"thread_id": f"ksession_{user_id}"}}
    input_data = {
        "messages": [{"role": "user", "content": question}],
        "user_id": user_id,
    }

    t0 = time.time()
    last_state = {}
    async for chunk in graph.astream(input_data, config, stream_mode="values"):
        last_state = chunk
    elapsed = time.time() - t0

    rewritten = last_state.get("rewritten_question", "")
    intent = last_state.get("intent", "")
    db_results = last_state.get("db_results", [])
    rag_docs = last_state.get("rag_docs", [])
    answer = last_state.get("final_answer", "")

    print(f"\n  ⏱️  耗时: {elapsed:.1f}s")
    print(f"  🔄 重写问题: {rewritten if rewritten != question else '(未重写)'}")
    print(f"  🎯 意图: {intent}")
    print(f"  📊 DB结果: {len(db_results)} 条")
    if db_results:
        for r in db_results[:5]:
            print(f"    - [{r.get('product_id','')}] {r.get('product_name','')}")
    print(f"  📚 Milvus RAG结果: {len(rag_docs)} 条")
    if rag_docs:
        for d in rag_docs[:3]:
            src = d.get("source", d.get("collection", "?"))
            print(f"    - [{src}] (相关度:{d.get('score',0):.2f}) {d.get('content','')[:80]}...")

    if answer:
        print(f"\n  📝 最终回答 ({len(answer)}字符):")
        print_line("-")
        for line in answer.split("\n")[:30]:
            print(f"    {line}")
        if len(answer.split("\n")) > 30:
            print(f"    ... (共 {len(answer.splitlines())} 行)")
        print_line("-")

    return last_state


async def main() -> None:
    print_line("═")
    print("  知识问答 Agent · 本地集成测试")
    print("  (加载 .env，走真实 LLM / MySQL / Milvus RAG / PG Store)")
    print_line("═")

    checks = {
        "DASHSCOPE_API_KEY": bool(os.getenv("DASHSCOPE_API_KEY")),
        "MYSQL_HOST": os.getenv("MYSQL_HOST", ""),
        "MILVUS_HOST": os.getenv("MILVUS_HOST", ""),
        "POSTGRES_URI": PG_CONN_STRING,
    }
    for k, v in checks.items():
        status = "✅" if v else "❌"
        print(f"  {status} {k}: {v if k in ('MYSQL_HOST', 'MILVUS_HOST', 'POSTGRES_URI') else ('已设置' if v else '未设置')}")

    from knowledge_agent.graph import build_graph

    test_cases = [
        {"label": "测试 1/5: 产品属性查询(DB) - 重疾险价格", "question": "有哪些适合30岁程序员的重疾险？保费不要超过5000", "user_id": "kuser_001"},
        {"label": "测试 2/5: 概念解释(RAG) - 等待期", "question": "保险的等待期是什么意思？重疾险的等待期一般是多久？", "user_id": "kuser_002"},
        {"label": "测试 3/5: 理赔规则(RAG) - 理赔流程", "question": "买了重疾险之后如果确诊了癌症，怎么申请理赔？流程是什么？", "user_id": "kuser_003"},
        {"label": "测试 4/5: 条款解释(RAG) - 免责条款", "question": "什么情况下重疾险不赔付？有哪些免责条款？", "user_id": "kuser_004"},
        {"label": "测试 5/5: 产品详情(DB) - 安心保年龄限制", "question": "安心保·重疾险适合多大年龄的人投保？", "user_id": "kuser_005"},
    ]

    try:
        async with get_pg_store() as store:
            graph = build_graph(store=store)
            print("  ✅ PG Store 已连接，跨会话记忆已启用")

            for tc in test_cases:
                await run_one(graph, tc["question"], tc["user_id"], tc["label"])

            # ── 验证持久化 ──
            print_header("验证 PG Store 持久化")
            memory = UserMemoryStore(store)
            for uid in ["kuser_001", "kuser_002"]:
                interactions = await memory.get_recent_interactions(uid, limit=3)
                print(f"  📝 {uid} 最近交互: {len(interactions)} 条")
                for inter in interactions:
                    print(f"    - [{inter.get('agent', '?')}] {inter.get('question', '')[:50]}... → 意图:{inter.get('intent', '?')}")
    except Exception as e:
        print(f"  ⚠️  PG Store 连接失败: {e}")
        print("  回退到无 Store 模式运行...")
        graph = build_graph(store=None)
        for tc in test_cases[:2]:
            await run_one(graph, tc["question"], tc["user_id"], tc["label"])

    print_header("测试完成 ✅")


def run_local_test() -> None:
    import selectors
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))


if __name__ == "__main__":
    run_local_test()
