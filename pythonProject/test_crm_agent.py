"""
CRM Agent — 本地测试（加载 .env，走真实 LLM + mock 客户数据）

流程: load_customer → analyze_sentiment → predict_churn → identify_upsell → generate_report

用法:
    cd pythonProject
    python test_crm_agent.py
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


def print_line(char: str = "─", width: int = 64) -> None:
    print(char * width)


def print_header(title: str) -> None:
    print()
    print_line("═")
    print(f"  {title}")
    print_line("═")


async def run_one(graph, user_id: str, label: str) -> dict:
    print_header(label)

    config = {"configurable": {"thread_id": f"crmsession_{user_id}"}}
    input_data = {
        "messages": [{"role": "user", "content": f"分析客户 {user_id}"}],
        "user_id": user_id,
    }

    t0 = time.time()
    last_state = {}
    async for chunk in graph.astream(input_data, config, stream_mode="values"):
        last_state = chunk
    elapsed = time.time() - t0

    profile = last_state.get("customer_profile", {})
    policies = last_state.get("policies", [])
    sentiment = last_state.get("sentiment_summary", "")
    churn_risk = last_state.get("churn_risk", 0)
    time_nodes = last_state.get("key_time_nodes", [])
    upsells = last_state.get("upsell_opportunities", [])
    report = last_state.get("crm_report", "")

    print(f"\n  ⏱️  耗时: {elapsed:.1f}s")
    print(f"  👤 客户: {profile.get('name','?')}, {profile.get('age','?')}岁, "
          f"{profile.get('occupation','?')}, 等级{profile.get('membership_level','?')}")
    print(f"  💰 年保费: {profile.get('total_premium', 0)}元")
    print(f"\n  📋 保单 ({len(policies)}份):")
    for p in policies:
        status_icon = {"active": "🟢", "expiring_soon": "🟡", "expired": "🔴"}.get(p.get("status", ""), "⚪")
        print(f"    {status_icon} {p.get('product_name','')} - {p.get('status','')}"
              f" (到期: {p.get('end_date','')})")

    print(f"\n  📊 情感分析: {sentiment[:200]}...")
    print(f"\n  ⚠️  流失风险: {churn_risk}/100")
    if time_nodes:
        print(f"  🔔 关键节点:")
        for n in time_nodes[:5]:
            print(f"    - {n.get('type','')}: {n.get('policy_name','')} "
                  f"({n.get('days_left', '?')}天后, 紧急度: {n.get('urgency','')})")

    print(f"\n  💡 加购机会 ({len(upsells)}个):")
    for u in upsells[:5]:
        print(f"    [{u.get('priority','')}] {u.get('product_type','')}: {u.get('reason','')[:60]}")

    if report:
        print(f"\n  📝 CRM报告 ({len(report)}字符):")
        print_line("-")
        for line in report.split("\n")[:35]:
            print(f"    {line}")
        if len(report.split("\n")) > 35:
            print(f"    ... (共 {len(report.splitlines())} 行)")
        print_line("-")

    return last_state


async def main() -> None:
    print_line("═")
    print("  CRM Agent · 本地集成测试")
    print("  (加载 .env，走真实 LLM + mock 客户数据)")
    print_line("═")

    checks = {"DASHSCOPE_API_KEY": bool(os.getenv("DASHSCOPE_API_KEY"))}
    for k, v in checks.items():
        status = "✅" if v else "❌"
        print(f"  {status} {k}: {'已设置' if v else '未设置'}")

    from crm_agent.graph import build_graph
    graph = build_graph()

    test_cases = [{"label": "测试 1/1: CRM 客户综合洞察", "user_id": "cust_001"}]
    for tc in test_cases:
        await run_one(graph, tc["user_id"], tc["label"])

    print_header("测试完成 ✅")


def run_local_test() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run_local_test()
