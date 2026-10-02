"""Deterministic, composable household protection planning workflow."""

import json
import operator
import re
import time
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field

from agents.schemas import (
    AggregateAgentInput,
    AggregateAgentOutput,
    CRMAgentInput,
    CRMAgentOutput,
    ComplianceAgentInput,
    ComplianceAgentOutput,
    CoverageGap,
    CoverageGapAgentInput,
    CoverageGapAgentOutput,
    FamilyProfile,
    KnowledgeAgentInput,
    KnowledgeAgentOutput,
    ProductAgentInput,
    ProductAgentOutput,
    ProfileAgentInput,
    ProfileAgentOutput,
)
from harness.dependencies import AgentDependencies
from harness.errors import DependencyUnavailableError
from harness.registry import AgentRegistry, agent_registry
from tools.base import ToolCallContext
from tools.policy_tools import Evidence
from tools.product_tools import Product


class PlanTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    agent: str
    goal: str
    depends_on: list[str] = Field(default_factory=list)
    required: bool = True


class CoverageRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: Literal["critical_illness", "medical", "accident", "life"]
    insurance_type: str
    recommended_coverage: float = Field(gt=0)
    priority: Literal["high", "medium", "low"]
    rationale: str


class CoverageRuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    disclaimer: str
    rules: list[CoverageRule]


class AgentTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent: str
    wave: int = Field(ge=1)
    status: Literal["completed", "degraded"]
    started_at_ns: int
    finished_at_ns: int


class FamilyPlanState(TypedDict, total=False):
    messages: list[Any]
    user_id: str
    plan: list[dict[str, Any]]
    profile: dict[str, Any]
    portfolio: list[dict[str, Any]]
    crm_available: bool
    coverage_gaps: list[dict[str, Any]]
    disclaimer: str
    products: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    draft: str
    compliance: dict[str, Any]
    final_answer: str
    handled_by: list[str]
    warnings: Annotated[list[str], operator.add]
    agent_trace: Annotated[list[dict[str, Any]], operator.add]


def fixed_family_plan() -> list[PlanTask]:
    """Return the explainable Day 4 plan; no LLM can change required tasks."""

    return [
        PlanTask(
            task_id="profile",
            agent="profile_agent",
            goal="提取并校验家庭投保画像",
            depends_on=[],
        ),
        PlanTask(
            task_id="crm",
            agent="crm_agent",
            goal="读取现有保单组合",
            depends_on=[],
            required=False,
        ),
        PlanTask(
            task_id="coverage_gap",
            agent="coverage_gap_agent",
            goal="根据画像和现有保单计算保障缺口",
            depends_on=["profile", "crm"],
        ),
        PlanTask(
            task_id="product",
            agent="product_agent",
            goal="查询匹配缺口的在售产品",
            depends_on=["coverage_gap"],
        ),
        PlanTask(
            task_id="knowledge",
            agent="knowledge_agent",
            goal="检索条款依据与注意事项",
            depends_on=["coverage_gap"],
            required=False,
        ),
        PlanTask(
            task_id="aggregate",
            agent="aggregate",
            goal="聚合画像、缺口、产品与证据",
            depends_on=["product", "knowledge"],
        ),
        PlanTask(
            task_id="compliance",
            agent="compliance_agent",
            goal="检查事实边界和建议措辞",
            depends_on=["aggregate"],
        ),
    ]


def load_coverage_rules(path: str | Path | None = None) -> CoverageRuleSet:
    resolved = Path(path) if path else Path(__file__).with_name("coverage_rules.json")
    return CoverageRuleSet.model_validate_json(resolved.read_text(encoding="utf-8"))


def build_family_plan_graph(
    *,
    dependencies: AgentDependencies | None,
    registry: AgentRegistry | None = None,
    rules: CoverageRuleSet | None = None,
    checkpointer: Any = None,
    store: Any = None,
) -> Any:
    """Build a fixed graph with two explicit parallel execution waves."""

    resolved_registry = registry or agent_registry
    resolved_rules = rules or load_coverage_rules()
    workflow = StateGraph(FamilyPlanState)

    def gateway() -> Any:
        if dependencies is None or dependencies.tool_gateway is None:
            raise DependencyUnavailableError(
                "Family planning requires the governed Tool Gateway",
                details={"dependency": "tool_gateway"},
            )
        return dependencies.tool_gateway

    async def planner_node(_state: FamilyPlanState) -> dict[str, Any]:
        return {"plan": [task.model_dump(mode="json") for task in fixed_family_plan()]}

    async def profile_node(
        state: FamilyPlanState,
        config: RunnableConfig | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter_ns()
        conversation = _latest_user_text(state.get("messages", []))
        stored_profile_json = "{}"
        if state.get("user_id"):
            stored = await resolved_registry.execute_tool(
                "profile_agent",
                gateway(),
                "get_profile_memory",
                {"user_id": state["user_id"]},
                context=ToolCallContext.from_config(config),
            )
            stored_profile_json = json.dumps(
                stored.data.get("profile") or {},
                ensure_ascii=False,
            )
        agent_input = resolved_registry.validate_input(
            "profile_agent",
            ProfileAgentInput(
                conversation=conversation,
                stored_profile_json=stored_profile_json,
            ),
        )
        tool_result = await resolved_registry.execute_tool(
            "profile_agent",
            gateway(),
            "extract_customer_profile",
            agent_input.model_dump(),
            context=ToolCallContext.from_config(config),
        )
        profile_data = dict(tool_result.data)
        if profile_data.get("age") is None:
            supplied = interrupt(
                {
                    "type": "missing_family_profile_fields",
                    "fields": ["age"],
                    "question": "请补充家庭保障规划对象的年龄。",
                }
            )
            if isinstance(supplied, dict):
                profile_data.update(supplied)
            else:
                profile_data["age"] = supplied
        output = resolved_registry.validate_output(
            "profile_agent",
            ProfileAgentOutput(profile=FamilyProfile.model_validate(profile_data)),
        )
        return {
            "profile": output.profile.model_dump(mode="json"),
            "agent_trace": [_trace("profile_agent", 1, started)],
        }

    async def crm_node(
        state: FamilyPlanState,
        config: RunnableConfig | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter_ns()
        user_id = state.get("user_id") or "anonymous"
        agent_input = resolved_registry.validate_input(
            "crm_agent",
            CRMAgentInput(user_id=user_id),
        )
        try:
            result = await resolved_registry.execute_tool(
                "crm_agent",
                gateway(),
                "get_customer_policy_portfolio",
                agent_input.model_dump(),
                context=ToolCallContext.from_config(config),
            )
            output = resolved_registry.validate_output(
                "crm_agent",
                CRMAgentOutput(portfolio=result.data.get("policies", [])),
            )
            status: Literal["completed", "degraded"] = "completed"
        except DependencyUnavailableError:
            output = resolved_registry.validate_output(
                "crm_agent",
                CRMAgentOutput(
                    portfolio=[],
                    crm_available=False,
                    warnings=["CRM 数据暂不可用，本次规划未考虑已有保单。"],
                ),
            )
            status = "degraded"
        return {
            "portfolio": output.portfolio,
            "crm_available": output.crm_available,
            "warnings": output.warnings,
            "agent_trace": [_trace("crm_agent", 1, started, status)],
        }

    async def coverage_gap_node(
        state: FamilyPlanState,
        config: RunnableConfig | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter_ns()
        agent_input = resolved_registry.validate_input(
            "coverage_gap_agent",
            CoverageGapAgentInput(
                profile=FamilyProfile.model_validate(state["profile"]),
                portfolio=state.get("portfolio", []),
            ),
        )
        await resolved_registry.execute_tool(
            "coverage_gap_agent",
            gateway(),
            "calculate_coverage_gap",
            {"portfolio": agent_input.portfolio},
            context=ToolCallContext.from_config(config),
        )
        gaps = _calculate_detailed_gaps(agent_input.portfolio, resolved_rules)
        output = resolved_registry.validate_output(
            "coverage_gap_agent",
            CoverageGapAgentOutput(
                coverage_gaps=gaps,
                disclaimer=resolved_rules.disclaimer,
            ),
        )
        return {
            "coverage_gaps": [item.model_dump(mode="json") for item in output.coverage_gaps],
            "disclaimer": output.disclaimer,
            "agent_trace": [_trace("coverage_gap_agent", 2, started)],
        }

    async def product_node(
        state: FamilyPlanState,
        config: RunnableConfig | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter_ns()
        agent_input = resolved_registry.validate_input(
            "product_agent",
            ProductAgentInput(
                profile=FamilyProfile.model_validate(state["profile"]),
                coverage_gaps=[CoverageGap.model_validate(item) for item in state["coverage_gaps"]],
            ),
        )
        target_type = agent_input.profile.insurance_type or _target_insurance_type(
            agent_input.coverage_gaps,
            resolved_rules,
        )
        result = await resolved_registry.execute_tool(
            "product_agent",
            gateway(),
            "search_active_insurance_products",
            {
                "insurance_type": target_type,
                "age": agent_input.profile.age,
                "occupation": agent_input.profile.occupation,
                "budget": agent_input.profile.budget,
                "limit": 10,
            },
            context=ToolCallContext.from_config(config),
        )
        output = resolved_registry.validate_output(
            "product_agent",
            ProductAgentOutput(products=[Product.model_validate(item) for item in result.data]),
        )
        return {
            "products": [item.model_dump(mode="json") for item in output.products],
            "agent_trace": [_trace("product_agent", 3, started)],
        }

    async def knowledge_node(
        state: FamilyPlanState,
        config: RunnableConfig | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter_ns()
        agent_input = resolved_registry.validate_input(
            "knowledge_agent",
            KnowledgeAgentInput(
                coverage_gaps=[CoverageGap.model_validate(item) for item in state["coverage_gaps"]]
            ),
        )
        query = "、".join(gap.category for gap in agent_input.coverage_gaps if gap.gap > 0)
        try:
            result = await resolved_registry.execute_tool(
                "knowledge_agent",
                gateway(),
                "retrieve_policy_evidence",
                {
                    "query": f"家庭保障规划 {query} 条款 免责 等待期",
                    "product_ids": [],
                    "top_k": 10,
                },
                context=ToolCallContext.from_config(config),
            )
            evidence = [Evidence.model_validate(item) for item in result.data]
            warnings = [] if evidence else ["未检索到可验证的条款依据，不生成条款引用。"]
            status: Literal["completed", "degraded"] = "completed"
        except DependencyUnavailableError:
            evidence = []
            warnings = ["知识库暂不可用，不生成伪造条款或引用。"]
            status = "degraded"
        output = resolved_registry.validate_output(
            "knowledge_agent",
            KnowledgeAgentOutput(evidence=evidence, warnings=warnings),
        )
        return {
            "evidence": [item.model_dump(mode="json") for item in output.evidence],
            "warnings": output.warnings,
            "agent_trace": [_trace("knowledge_agent", 3, started, status)],
        }

    async def aggregate_node(state: FamilyPlanState) -> dict[str, Any]:
        started = time.perf_counter_ns()
        agent_input = AggregateAgentInput(
            profile=FamilyProfile.model_validate(state["profile"]),
            portfolio=state.get("portfolio", []),
            coverage_gaps=[CoverageGap.model_validate(item) for item in state["coverage_gaps"]],
            products=[Product.model_validate(item) for item in state.get("products", [])],
            evidence=[Evidence.model_validate(item) for item in state.get("evidence", [])],
            warnings=state.get("warnings", []),
        )
        output = AggregateAgentOutput(draft=_aggregate_plan(agent_input, state["disclaimer"]))
        return {
            "draft": output.draft,
            "agent_trace": [_trace("aggregate", 4, started)],
        }

    async def compliance_node(state: FamilyPlanState) -> dict[str, Any]:
        started = time.perf_counter_ns()
        agent_input = resolved_registry.validate_input(
            "compliance_agent",
            ComplianceAgentInput(
                draft=state["draft"],
                products=[Product.model_validate(item) for item in state.get("products", [])],
                evidence=[Evidence.model_validate(item) for item in state.get("evidence", [])],
                warnings=state.get("warnings", []),
            ),
        )
        issues: list[str] = []
        blocking_issues: list[str] = []
        if not agent_input.products:
            issues.append("没有查询到匹配的在售产品")
        if not agent_input.evidence:
            issues.append("没有可验证的条款证据")
        if "不构成核保结论或正式保险建议" not in agent_input.draft:
            blocking_issues.append("缺少演示规则与非正式建议声明")
        if re.search(r"保证收益|一定承保|百分之百理赔", agent_input.draft):
            blocking_issues.append("包含禁止的承诺性措辞")
        approved = not blocking_issues
        output = resolved_registry.validate_output(
            "compliance_agent",
            ComplianceAgentOutput(
                approved=approved,
                final_answer=(
                    agent_input.draft
                    if approved
                    else "本次规划未通过合规检查，请联系人工保险顾问复核。"
                ),
                issues=[*blocking_issues, *issues],
                warnings=agent_input.warnings,
            ),
        )
        handled_by = [
            "profile_agent",
            "crm_agent",
            "coverage_gap_agent",
            "product_agent",
            "knowledge_agent",
            "compliance_agent",
        ]
        return {
            "compliance": output.model_dump(mode="json"),
            "final_answer": output.final_answer,
            "handled_by": handled_by,
            "agent_trace": [_trace("compliance_agent", 5, started)],
        }

    workflow.add_node("planner", planner_node)
    workflow.add_node("profile_agent", profile_node)
    workflow.add_node("crm_agent", crm_node)
    workflow.add_node("coverage_gap_agent", coverage_gap_node)
    workflow.add_node("product_agent", product_node)
    workflow.add_node("knowledge_agent", knowledge_node)
    workflow.add_node("aggregate", aggregate_node)
    workflow.add_node("compliance_agent", compliance_node)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "profile_agent")
    workflow.add_edge("planner", "crm_agent")
    workflow.add_edge(["profile_agent", "crm_agent"], "coverage_gap_agent")
    workflow.add_edge("coverage_gap_agent", "product_agent")
    workflow.add_edge("coverage_gap_agent", "knowledge_agent")
    workflow.add_edge(["product_agent", "knowledge_agent"], "aggregate")
    workflow.add_edge("aggregate", "compliance_agent")
    workflow.add_edge("compliance_agent", END)

    return workflow.compile(checkpointer=checkpointer, store=store)


def _trace(
    agent: str,
    wave: int,
    started_at_ns: int,
    status: Literal["completed", "degraded"] = "completed",
) -> dict[str, Any]:
    return AgentTrace(
        agent=agent,
        wave=wave,
        status=status,
        started_at_ns=started_at_ns,
        finished_at_ns=time.perf_counter_ns(),
    ).model_dump(mode="json")


def _latest_user_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, dict):
            if message.get("role", message.get("type")) in ("user", "human"):
                return str(message.get("content", ""))
        elif getattr(message, "type", "") == "human":
            return str(getattr(message, "content", ""))
    return ""


def _calculate_detailed_gaps(
    portfolio: list[dict[str, Any]],
    rules: CoverageRuleSet,
) -> list[CoverageGap]:
    active = [
        policy
        for policy in portfolio
        if policy.get("status") in ("active", "expiring_soon")
    ]
    gaps: list[CoverageGap] = []
    for rule in rules.rules:
        current = sum(
            float(policy.get("insured_amount") or 0)
            for policy in active
            if policy.get("insurance_type") == rule.insurance_type
        )
        gap = max(0.0, rule.recommended_coverage - current)
        gaps.append(
            CoverageGap(
                category=rule.category,
                current_coverage=current,
                recommended_coverage=rule.recommended_coverage,
                gap=gap,
                priority="low" if gap == 0 else rule.priority,
                rationale=f"{rule.rationale} {rules.disclaimer}",
            )
        )
    return gaps


def _target_insurance_type(
    gaps: list[CoverageGap],
    rules: CoverageRuleSet,
) -> str | None:
    priority_order = {"high": 0, "medium": 1, "low": 2}
    candidates = sorted(
        (gap for gap in gaps if gap.gap > 0),
        key=lambda item: (priority_order[item.priority], -item.gap),
    )
    if not candidates:
        return None
    category = candidates[0].category
    return next(rule.insurance_type for rule in rules.rules if rule.category == category)


def _aggregate_plan(value: AggregateAgentInput, disclaimer: str) -> str:
    profile = value.profile
    lines = [
        "## 家庭保障规划（演示版）",
        "",
        f"规划对象：{profile.age}岁"
        + (f"，职业{profile.occupation}" if profile.occupation else "")
        + (f"，年度预算约{profile.budget:.0f}元" if profile.budget is not None else ""),
        "",
        "### 保障缺口",
    ]
    for gap in value.coverage_gaps:
        lines.append(
            f"- {gap.category}: 当前{gap.current_coverage:.0f}元，"
            f"演示建议{gap.recommended_coverage:.0f}元，缺口{gap.gap:.0f}元，"
            f"优先级{gap.priority}。"
        )
    lines.extend(["", "### 在售产品候选"])
    if value.products:
        for product in value.products:
            lines.append(
                f"- {product.product_name}（{product.product_id}）："
                f"最低保费{product.min_price or 0:.0f}元。"
            )
    else:
        lines.append("- 当前条件下没有查询到匹配的在售产品。")
    lines.extend(["", "### 条款证据"])
    if value.evidence:
        for evidence in value.evidence[:5]:
            lines.append(f"- {evidence.content}（来源：{evidence.source or '知识库'}）")
    else:
        lines.append("- 暂无可验证条款证据，不对等待期、免责或理赔范围作具体断言。")
    if value.warnings:
        lines.extend(["", "### 数据限制"])
        lines.extend(f"- {warning}" for warning in value.warnings)
    lines.extend(["", f"> {disclaimer}"])
    return "\n".join(lines)
