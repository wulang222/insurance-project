"""
保险推荐 Agent — 本地测试（加载 .env，走真实服务 + PG Store 持久化）

用法:
    cd pythonProject
    python test_agent.py
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

from insurance_agent.graph import build_graph
from insurance_agent.state import UserProfile
from shared.memory import get_pg_store, UserMemoryStore, PG_CONN_STRING


def print_line(char: str = "─", width: int = 64) -> None:
    print(char * width)


def print_header(title: str) -> None:
    print()
    print_line("═")
    print(f"  {title}")
    print_line("═")


def format_profile(p: UserProfile | None) -> str:
    if p is None:
        return "未提取到"
    return f"{p.age}岁 / {p.occupation} / 预算{p.budget}元/年 / {p.insurance_type}"


def format_products(products: list[dict]) -> None:
    if not products:
        print("    (无匹配产品)")
        return
    for i, p in enumerate(products, 1):
        rag_len = len(p.get("rag_content", ""))
        print(f"    {i}. [{p['product_id']}] {p['product_name']}")
        print(f"       险种: {p['insurance_type']} | "
              f"年龄: {p['min_age']}-{p['max_age']}岁 | "
              f"保费: {p['min_price']}-{p['max_price']}元/年")
        print(f"       描述: {p.get('description', '')[:80]}")
        print(f"       RAG上下文: {rag_len} 字符")


async def run_one(graph, message: str, user_id: str, label: str, show_full: bool = False) -> dict:
    print_header(label)
    print(f"\n  💬 用户: {message}")

    config = {"configurable": {"thread_id": f"session_{user_id}"}}
    input_data = {
        "messages": [{"role": "user", "content": message}],
        "user_id": user_id,
    }

    t0 = time.time()
    last_state = {}
    async for chunk in graph.astream(input_data, config, stream_mode="values"):
        last_state = chunk
    elapsed = time.time() - t0

    profile = last_state.get("user_profile")
    products = last_state.get("matched_products", [])
    rec = last_state.get("final_recommendation", "")

    print(f"\n  ⏱️  耗时: {elapsed:.1f}s")
    print(f"  👤 画像: {format_profile(profile)}")
    print(f"  📦 匹配产品: {len(products)} 款")
    format_products(products)

    if show_full and rec:
        print(f"\n  📝 完整推荐 ({len(rec)}字符):")
        print_line("-")
        for line in rec.split("\n")[:40]:
            print(f"    {line}")
        if len(rec.split("\n")) > 40:
            print(f"    ... (共 {len(rec.splitlines())} 行)")
        print_line("-")
    elif rec:
        print(f"  📝 推荐摘要: {rec[:200]}...")

    return last_state


async def main() -> None:
    print_line("═")
    print("  保险推荐 Agent · 本地集成测试")
    print("  (加载 .env，走真实 LLM / MySQL / Milvus / PG Store)")
    print_line("═")

    checks = {
        "DASHSCOPE_API_KEY": bool(os.getenv("DASHSCOPE_API_KEY")),
        "MYSQL_HOST": os.getenv("MYSQL_HOST", ""),
        "MILVUS_HOST": os.getenv("MILVUS_HOST", ""),
        "MILVUS_COLLECTION": os.getenv("MILVUS_COLLECTION", "insurance_info"),
        "POSTGRES_URI": PG_CONN_STRING,
    }
    for k, v in checks.items():
        status = "✅" if v else "❌"
        print(f"  {status} {k}: {v if k in ('MYSQL_HOST', 'MILVUS_HOST', 'MILVUS_COLLECTION', 'POSTGRES_URI') else ('已设置' if v else '未设置')}")

    # ── 创建 PG Store（跨会话记忆持久化） ──
    try:
        async with get_pg_store() as store:
            graph = build_graph(store=store)
            print("  ✅ PG Store 已连接，跨会话记忆已启用")

            test_cases = [
                {"label": "测试 1/4: 完整信息(程序员买重疾险)", "message": "我今年28岁，是程序员，预算5000元/年，想买重疾险", "user_id": "test_user_001", "full": True},
                {"label": "测试 2/4: 教师买医疗险(低预算)", "message": "我45岁，是教师，每年预算800元，想买一份医疗险", "user_id": "test_user_002", "full": False},
                {"label": "测试 3/4: 销售经理买意外险", "message": "30岁，销售经理，经常出差，预算300元左右/年，想买意外险", "user_id": "test_user_003", "full": False},
                {"label": "测试 4/4: 月预算 + 年龄边缘", "message": "25岁，刚毕业的设计师，每个月能拿300块买保险，想买重疾险", "user_id": "test_user_004", "full": True},
            ]

            for tc in test_cases:
                await run_one(graph, tc["message"], tc["user_id"], tc["label"], tc["full"])

            # ── 验证持久化 ──
            print_header("验证 PG Store 持久化")
            memory = UserMemoryStore(store)
            for uid in ["test_user_001", "test_user_004"]:
                profile = await memory.load_user_profile(uid)
                if profile:
                    print(f"  ✅ {uid}: 画像已持久化 → {profile.get('age')}岁, {profile.get('occupation')}, {profile.get('insurance_type')}")
                else:
                    print(f"  ⚠️  {uid}: 未找到持久化画像（可能画像不完整导致未保存）")

            interactions = await memory.get_recent_interactions("test_user_001", limit=3)
            print(f"  📝 test_user_001 最近交互: {len(interactions)} 条")
    except Exception as e:
        print(f"  ⚠️  PG Store 连接失败: {e}")
        print("  回退到无 Store 模式运行...")
        graph = build_graph(store=None)
        for tc in [
            {"label": "测试 1/4: 重疾险", "message": "我今年28岁，是程序员，预算5000元/年，想买重疾险", "user_id": "test_user_001", "full": True},
        ]:
            await run_one(graph, tc["message"], tc["user_id"], tc["label"], tc["full"])

    print_header("测试完成 ✅")


def run_local_test() -> None:
    # Windows 上 Psycopg3 需要 SelectorEventLoop
    import selectors
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))


if __name__ == "__main__":
    run_local_test()
