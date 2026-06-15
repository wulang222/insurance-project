"""
Supervisor Agent — 本地测试（加载 .env，路由到子 Agent）

职责: 分析用户输入 → 动态路由到 insurance/knowledge/crm agent

用法:
    cd pythonProject
    python test_supervisor_agent.py
"""
from __future__ import annotations

import asyncio
import json
import os
import selectors
import sys
import time
from pathlib import Path

# ── 0. 环境准备 ──
from dotenv import load_dotenv
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)
print(f"✅ 已加载 .env: {_env_path}")

sys.path.insert(0, str(Path(__file__).parent / "src"))

from supervisor_agent.graph import build_graph
from shared.memory import get_pg_store, UserMemoryStore, PG_CONN_STRING


def print_line(char: str = "─", width: int = 72) -> None:
    print(char * width)


def print_header(title: str) -> None:
    print()
    print_line("═")
    print(f"  {title}")
    print_line("═")


async def run_one(graph, message: str, user_id: str, label: str, show_full: bool = False) -> dict:
    print_header(label)
    print(f"\n  💬 用户: {message}")

    config = {"configurable": {"thread_id": f"sup_{user_id}"}}
    input_data = {
        "messages": [{"role": "user", "content": message}],
        "user_id": user_id,
    }

    t0 = time.time()
    last_state = {}
    async for chunk in graph.astream(input_data, config, stream_mode="values"):
        last_state = chunk
    elapsed = time.time() - t0

    route = last_state.get("route", "?")
    route_reason = last_state.get("route_reason", "?")
    handled_by = last_state.get("handled_by", "?")
    answer = last_state.get("final_answer", "")

    print(f"\n  ⏱️  耗时: {elapsed:.1f}s")
    print(f"  🧭 路由: {route}")
    print(f"  📋 理由: {route_reason}")
    print(f"  🤖 执行: {handled_by}")

    # 打印子 agent 的部分关键结果
    child = last_state.get("child_result", {})
    if handled_by == "insurance_agent":
        profile = child.get("user_profile")
        products = child.get("matched_products", [])
        if profile:
            print(f"  👤 画像: {profile.age}岁 / {profile.occupation} / 预算{profile.budget}元 / {profile.insurance_type}")
        print(f"  📦 匹配: {len(products)} 款产品")
    elif handled_by == "knowledge_agent":
        intent = child.get("intent", "?")
        db_results = child.get("db_results", [])
        rag_docs = child.get("rag_docs", [])
        print(f"  🎯 意图: {intent}")
        print(f"  📊 DB: {len(db_results)}条  📚 RAG: {len(rag_docs)}条")
    elif handled_by == "crm_agent":
        churn = child.get("churn_risk", "?")
        upsells = child.get("upsell_opportunities", [])
        print(f"  ⚠️  流失: {churn}/100  💡 加购: {len(upsells)}个")

    if answer:
        preview = answer[:400].replace("\n", "\n    ")
        print(f"\n  📝 回答:")
        print(f"    {preview}")
        if len(answer) > 400:
            print(f"    ... (共 {len(answer)} 字符)")

    return last_state


async def main() -> None:
    print_line("═")
    print("  Supervisor Agent · 本地集成测试")
    print("  (加载 .env → 路由到 insurance / knowledge / crm agent)")
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

    test_cases = [
        # ── insurance_agent ──
        {
            "label": "测试 1/6: 路由→insurance | 保险推荐(含年龄职业预算)",
            "message": "我今年28岁，是程序员，预算5000元/年，想买重疾险",
            "user_id": "sup_001",
            "full": True,
        },
        {
            "label": "测试 2/6: 路由→insurance | 保险推荐(想买保险+个人需求)",
            "message": "最近想买一份意外险，我是销售经理，经常出差，预算300左右",
            "user_id": "sup_002",
            "full": False,
        },
        # ── knowledge_agent ──
        {
            "label": "测试 3/6: 路由→knowledge | 保险知识问答(等待期)",
            "message": "保险的等待期是什么意思？重疾险一般等待期多久？",
            "user_id": "sup_003",
            "full": False,
        },
        {
            "label": "测试 4/6: 路由→knowledge | 保险知识问答(理赔流程)",
            "message": "如果我确诊了重疾，怎么申请理赔？需要准备什么材料？",
            "user_id": "sup_004",
            "full": False,
        },
        # ── crm_agent ──
        {
            "label": "测试 5/6: 路由→crm | CRM客户分析",
            "message": "帮我分析一下用户cust_001的CRM情况，看看流失风险和续保问题",
            "user_id": "sup_005",
            "full": True,
        },
        # ── 边界场景 ──
        {
            "label": "测试 6/6: 路由→insurance | 边界(只有险种+预算，无年龄职业)",
            "message": "我想买重疾险，预算5000左右，有什么推荐的？",
            "user_id": "sup_006",
            "full": False,
        },
    ]

    try:
        async with get_pg_store() as store:
            graph = build_graph(store=store)
            print("  ✅ PG Store 已连接，跨会话记忆已启用")

            for tc in test_cases:
                await run_one(graph, tc["message"], tc["user_id"], tc["label"], tc["full"])

            # ── 验证路由统计 ──
            print_header("路由统计")
            routes_seen: dict[str, int] = {}
            for tc in test_cases:
                # 重新执行一次实际路由来收集统计（这里只打印预期）
                pass
            print("  预期路由分布: insurance=3, knowledge=2, crm=1")

    except Exception as e:
        print(f"  ⚠️  PG Store 连接失败: {e}")
        print("  回退到无 Store 模式运行...")
        graph = build_graph(store=None)
        for tc in test_cases[:4]:
            await run_one(graph, tc["message"], tc["user_id"], tc["label"], tc["full"])

    print_header("测试完成 ✅")


def run_local_test() -> None:
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))


if __name__ == "__main__":
    run_local_test()
