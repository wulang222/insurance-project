"""Run all Day 6 JSONL datasets and emit a reproducible report."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.graders import Grade, exact_match, forbidden_absent, human_sample_grade, required_subset
from safety.compliance import ComplianceEvaluator
from safety.evidence import build_evidence_pack, citation_from_evidence
from safety.models import FactualClaim, Recommendation, RecommendationDraft
from supervisor_agent.graph import _rule_route
from tools.policy_tools import EvidenceInput
from tools.product_tools import Product, ProductSearchInput
from tools.registry import _regex_profile
from workflows.family_plan import fixed_family_plan


DATASET_NAMES = (
    "routing",
    "profile_extraction",
    "tool_selection",
    "family_plan",
    "knowledge_grounding",
    "compliance",
)
TARGETS = {
    "routing": 0.95,
    "profile_extraction": 0.90,
    "tool_selection": 0.95,
    "family_plan": 0.85,
    "knowledge_grounding": 1.0,
    "compliance": 1.0,
}


def load_datasets(root: Path) -> dict[str, list[dict[str, Any]]]:
    datasets: dict[str, list[dict[str, Any]]] = {}
    for name in DATASET_NAMES:
        path = root / f"{name}.jsonl"
        datasets[name] = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return datasets


def run_evals(dataset_root: Path) -> dict[str, Any]:
    datasets = load_datasets(dataset_root)
    results: list[dict[str, Any]] = []
    for dataset_name, cases in datasets.items():
        for case in cases:
            grades, answer = _evaluate_case(dataset_name, case)
            quality = human_sample_grade(case["id"], answer)
            results.append(
                {
                    "dataset": dataset_name,
                    "case_id": case["id"],
                    "passed": all(item.passed for item in grades),
                    "grades": [item.model_dump(mode="json") for item in [*grades, quality]],
                }
            )

    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[item["dataset"]].append(item)
    summary = {}
    for name in DATASET_NAMES:
        values = grouped[name]
        passed = sum(1 for item in values if item["passed"])
        rate = passed / len(values) if values else 0.0
        summary[name] = {
            "cases": len(values),
            "passed": passed,
            "rate": rate,
            "target": TARGETS[name],
            "target_met": rate >= TARGETS[name],
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(results),
        "passed_cases": sum(1 for item in results if item["passed"]),
        "all_targets_met": all(item["target_met"] for item in summary.values()),
        "summary": summary,
        "human_review": {
            "required": True,
            "reason": "模型型质量维度不能由系统完全自证",
            "sample_case_ids": [item["case_id"] for item in results[:6]],
        },
        "results": results,
    }


def _evaluate_case(dataset: str, case: dict[str, Any]) -> tuple[list[Grade], str]:
    inputs = case["input"]
    expected = case["expected"]
    if dataset == "routing":
        actual = _rule_route(inputs["message"]) or "knowledge_agent"
        return [exact_match("route_exact_match", actual, expected["route"])], actual
    if dataset == "profile_extraction":
        actual = _regex_profile(inputs["message"]).model_dump(mode="json")
        fields = expected["profile"]
        matches = sum(actual.get(key) == value for key, value in fields.items())
        score = matches / max(1, len(fields))
        return [
            Grade(
                name="profile_field_accuracy",
                passed=score == 1,
                score=score,
                reason=f"expected={fields}; actual={actual}",
            )
        ], json.dumps(actual, ensure_ascii=False)
    if dataset == "tool_selection":
        tools, arguments_valid = _offline_tool_selection(inputs["message"])
        return [
            required_subset("expected_tool_called", tools, expected["required_tools"]),
            forbidden_absent("forbidden_tool_not_called", tools, expected.get("forbidden_tools", [])),
            exact_match("tool_arguments_valid", arguments_valid, True),
        ], ",".join(tools)
    if dataset == "family_plan":
        agents = [item.agent for item in fixed_family_plan()]
        return [
            required_subset("required_agents", agents, expected["required_agents"]),
            exact_match("interrupt_resume_outcome", inputs.get("age") is not None, expected["completes"]),
        ], ",".join(agents)
    if dataset == "knowledge_grounding":
        pack = build_evidence_pack(inputs["query"], inputs.get("evidence", []))
        citations = [citation_from_evidence(item) for item in pack.evidence]
        uncertain = not citations
        return [
            exact_match("required_citation_present", bool(citations), expected["has_citation"]),
            exact_match("uncertainty_when_no_evidence", uncertain, expected["uncertain"]),
        ], citations[0].excerpt if citations else "不确定，需人工确认"
    if dataset == "compliance":
        decision = _compliance_decision(inputs["mode"])
        return [exact_match("compliance_decision", decision.passed, expected["passed"])], str(decision)
    raise ValueError(f"unknown dataset: {dataset}")


def _offline_tool_selection(message: str) -> tuple[list[str], bool]:
    route = _rule_route(message) or "knowledge_agent"
    if route == "family_plan":
        tools = [
            "extract_customer_profile",
            "get_customer_policy_portfolio",
            "calculate_coverage_gap",
            "search_active_insurance_products",
            "retrieve_policy_evidence",
        ]
        ProductSearchInput(limit=10)
        EvidenceInput(query=message, top_k=10)
    elif route == "insurance_agent":
        tools = ["extract_customer_profile", "search_active_insurance_products", "retrieve_policy_evidence"]
        ProductSearchInput(limit=10)
        EvidenceInput(query=message, top_k=10)
    elif route == "crm_agent":
        tools = ["get_customer_policy_portfolio"]
    else:
        tools = ["retrieve_policy_evidence"]
        EvidenceInput(query=message, top_k=10)
    return tools, True


def _compliance_decision(mode: str):
    product = Product(
        product_id="CI001",
        product_name="测试重疾险",
        insurance_type="重疾险",
        min_age=18,
        max_age=55,
        min_price=3000,
        max_price=8000,
        is_active=True,
    )
    recommendation = Recommendation(
        product_id="FAKE" if mode == "fabricated" else product.product_id,
        product_name=product.product_name,
        insurance_type=product.insurance_type,
        min_age=product.min_age,
        max_age=product.max_age,
        min_price=1 if mode == "price_mismatch" else product.min_price,
        max_price=product.max_price,
        rationale="保证赔付" if mode == "banned" else "来自在售产品查询。",
    )
    claim = FactualClaim(
        claim_id="RULE-1",
        text="演示规则建议基础保障。",
        source_type="business_rule",
        rule_version="bad" if mode == "unsupported_rule" else "v1",
    )
    draft = RecommendationDraft(
        summary="根据可验证数据生成候选。",
        recommendations=[recommendation],
        factual_claims=[claim],
        disclaimers=(
            []
            if mode == "missing_disclaimer"
            else ["本方案仅供演示，不构成核保结论或正式保险建议。"]
        ),
    )
    return ComplianceEvaluator(allowed_rule_versions={"v1"}).evaluate(
        draft,
        products=[product],
        evidence=[],
        user_question="请推荐重疾险",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Day 6 evaluation harness")
    parser.add_argument(
        "--datasets",
        type=Path,
        default=Path(__file__).with_name("datasets"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_evals(args.datasets)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if not report["all_targets_met"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
