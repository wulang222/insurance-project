"""Two-level compliance evaluation with at most one targeted revision."""

from __future__ import annotations

import re
from typing import Any

from safety.models import (
    ComplianceDecision,
    ComplianceViolation,
    FactualClaim,
    Recommendation,
    RecommendationDraft,
)
from tools.policy_tools import Evidence
from tools.product_tools import Product


BANNED_PROMISES = (
    "保证赔付",
    "保证理赔",
    "保证收益",
    "一定可以投保",
    "一定承保",
    "百分之百理赔",
    "100%理赔",
)
SAFE_FALLBACK = (
    "当前产品或条款信息无法通过合规复核，结论不确定、需人工确认。"
    "请联系人工保险顾问，并以保险公司正式条款和核保结果为准。"
)


class ComplianceEvaluator:
    """Run deterministic fact checks before a separate semantic evaluator pass."""

    def __init__(self, *, allowed_rule_versions: set[str]) -> None:
        self.allowed_rule_versions = set(allowed_rule_versions)

    def evaluate(
        self,
        draft: RecommendationDraft,
        *,
        products: list[Product],
        evidence: list[Evidence],
        user_question: str,
        revision_count: int = 0,
    ) -> ComplianceDecision:
        code_violations, unsupported = self._code_checks(
            draft,
            products=products,
            evidence=evidence,
        )
        evaluator_violations = self._evaluator_checks(draft, user_question=user_question)
        violations = [*code_violations, *evaluator_violations]
        instructions = _revision_instructions(violations, unsupported)
        return ComplianceDecision(
            passed=not violations,
            violations=violations,
            unsupported_claims=unsupported,
            revision_instructions=instructions,
            revision_count=revision_count,
            code_checks_passed=not code_violations,
            evaluator_passed=not evaluator_violations,
        )

    def _code_checks(
        self,
        draft: RecommendationDraft,
        *,
        products: list[Product],
        evidence: list[Evidence],
    ) -> tuple[list[ComplianceViolation], list[str]]:
        violations: list[ComplianceViolation] = []
        unsupported: list[str] = []
        canonical = {item.product_id: item for item in products if item.is_active}
        evidence_by_document = {item.document_id: item for item in evidence}
        citation_by_id = {item.citation_id: item for item in draft.citations}

        if len(citation_by_id) != len(draft.citations):
            violations.append(_violation("DUPLICATE_CITATION", "引用 ID 必须唯一"))

        product_fields = (
            "product_name",
            "insurance_type",
            "min_age",
            "max_age",
            "min_price",
            "max_price",
        )
        for recommendation in draft.recommendations:
            product = canonical.get(recommendation.product_id)
            if product is None:
                violations.append(
                    _violation(
                        "PRODUCT_NOT_ACTIVE",
                        "推荐产品不存在或不在售",
                        product_id=recommendation.product_id,
                    )
                )
                continue
            for field_name in product_fields:
                if getattr(recommendation, field_name) != getattr(product, field_name):
                    violations.append(
                        _violation(
                            "PRODUCT_FIELD_MISMATCH",
                            f"推荐中的 {field_name} 与产品库不一致",
                            product_id=recommendation.product_id,
                        )
                    )

        for citation in draft.citations:
            item = evidence_by_document.get(citation.document_id)
            if item is None:
                violations.append(
                    _violation(
                        "CITATION_NOT_FOUND",
                        f"引用 {citation.citation_id} 在证据包中不存在",
                    )
                )
                continue
            if citation.excerpt not in item.content or citation.source_version != item.version:
                violations.append(
                    _violation(
                        "CITATION_MISMATCH",
                        f"引用 {citation.citation_id} 与原始证据不一致",
                    )
                )

        for claim in draft.factual_claims:
            supported = self._claim_supported(
                claim,
                canonical=canonical,
                evidence_by_document=evidence_by_document,
                citation_by_id=citation_by_id,
                violations=violations,
            )
            if not supported:
                unsupported.append(claim.text)

        serialized = str(draft.model_dump(mode="json"))
        for phrase in BANNED_PROMISES:
            if phrase in serialized:
                violations.append(
                    _violation("BANNED_PROMISE", f"包含禁止的承诺性措辞：{phrase}")
                )
        return violations, unsupported

    def _claim_supported(
        self,
        claim: FactualClaim,
        *,
        canonical: dict[str, Product],
        evidence_by_document: dict[str, Evidence],
        citation_by_id: dict[str, Any],
        violations: list[ComplianceViolation],
    ) -> bool:
        if claim.source_type == "product_field":
            product = canonical.get(claim.product_id or "")
            if product is None or claim.field_name not in Product.model_fields:
                violations.append(
                    _violation(
                        "UNSUPPORTED_PRODUCT_CLAIM",
                        "产品事实没有有效的产品库字段",
                        claim_id=claim.claim_id,
                        product_id=claim.product_id,
                    )
                )
                return False
            if getattr(product, claim.field_name) != claim.value:
                violations.append(
                    _violation(
                        "PRODUCT_CLAIM_MISMATCH",
                        "产品事实值与产品库不一致",
                        claim_id=claim.claim_id,
                        product_id=claim.product_id,
                    )
                )
                return False
            return True
        if claim.source_type == "business_rule":
            if claim.rule_version not in self.allowed_rule_versions:
                violations.append(
                    _violation(
                        "UNKNOWN_RULE_VERSION",
                        "业务规则版本不存在",
                        claim_id=claim.claim_id,
                    )
                )
                return False
            return True

        citation = citation_by_id.get(claim.citation_id or "")
        if citation is None:
            violations.append(
                _violation(
                    "CLAIM_CITATION_NOT_FOUND",
                    "条款事实未关联有效引用",
                    claim_id=claim.claim_id,
                )
            )
            return False
        item = evidence_by_document.get(citation.document_id)
        if item is None:
            return False
        if claim.product_id and item.product_id and claim.product_id != item.product_id:
            violations.append(
                _violation(
                    "CITATION_PRODUCT_MISMATCH",
                    "引用文档与声明的产品不一致",
                    claim_id=claim.claim_id,
                    product_id=claim.product_id,
                )
            )
            return False
        return True

    @staticmethod
    def _evaluator_checks(
        draft: RecommendationDraft,
        *,
        user_question: str,
    ) -> list[ComplianceViolation]:
        """Semantic evaluator boundary; may later be backed by a governed model call."""

        violations: list[ComplianceViolation] = []
        if not any("不构成" in item and ("正式" in item or "核保" in item) for item in draft.disclaimers):
            violations.append(
                _violation(
                    "MISSING_DISCLAIMER",
                    "缺少非正式建议或非核保结论声明",
                    level="evaluator",
                )
            )
        if not draft.summary.strip():
            violations.append(
                _violation("EMPTY_ANSWER", "未回答用户问题", level="evaluator")
            )
        if user_question.strip() and not (
            draft.recommendations or draft.factual_claims or "人工确认" in draft.summary
        ):
            violations.append(
                _violation(
                    "QUESTION_NOT_ANSWERED",
                    "回答没有覆盖用户的实际问题",
                    level="evaluator",
                )
            )
        return violations


def revise_draft_once(
    draft: RecommendationDraft,
    decision: ComplianceDecision,
    *,
    products: list[Product],
    evidence: list[Evidence],
    allowed_rule_versions: set[str],
) -> RecommendationDraft:
    """Apply only targeted, source-preserving corrections from one decision."""

    canonical = {item.product_id: item for item in products if item.is_active}
    evidence_by_document = {item.document_id: item for item in evidence}
    citation_by_id = {
        item.citation_id: item
        for item in draft.citations
        if item.document_id in evidence_by_document
        and item.excerpt in evidence_by_document[item.document_id].content
        and item.source_version == evidence_by_document[item.document_id].version
    }

    recommendations: list[Recommendation] = []
    for item in draft.recommendations:
        product = canonical.get(item.product_id)
        if product is None:
            continue
        recommendations.append(
            Recommendation(
                product_id=product.product_id,
                product_name=product.product_name,
                insurance_type=product.insurance_type,
                min_age=product.min_age,
                max_age=product.max_age,
                min_price=product.min_price,
                max_price=product.max_price,
                rationale=_remove_banned_promises(item.rationale),
            )
        )

    claims: list[FactualClaim] = []
    for claim in draft.factual_claims:
        if claim.source_type == "product_field":
            product = canonical.get(claim.product_id or "")
            if product is None or claim.field_name not in Product.model_fields:
                continue
            value = getattr(product, claim.field_name)
            claims.append(
                claim.model_copy(
                    update={
                        "value": value,
                        "text": f"{product.product_name} 的 {claim.field_name} 为 {value}",
                    }
                )
            )
        elif claim.source_type == "business_rule":
            if claim.rule_version in allowed_rule_versions:
                claims.append(claim)
        else:
            citation = citation_by_id.get(claim.citation_id or "")
            if citation is None:
                continue
            item = evidence_by_document[citation.document_id]
            if claim.product_id and item.product_id and claim.product_id != item.product_id:
                continue
            claims.append(claim)

    used_citation_ids = {
        claim.citation_id for claim in claims if claim.source_type == "citation"
    }
    citations = [
        item for citation_id, item in citation_by_id.items() if citation_id in used_citation_ids
    ]
    disclaimers = [_remove_banned_promises(item) for item in draft.disclaimers]
    if not any("不构成" in item for item in disclaimers):
        disclaimers.append("本方案仅供演示，不构成核保结论或正式保险建议。")
    if not evidence:
        disclaimers.append("未检索到可验证条款，相关信息不确定，需人工确认。")

    summary = _remove_banned_promises(draft.summary)
    if not recommendations:
        summary = "当前没有可由在售产品数据验证的推荐，需人工确认。"
    # Keep the revision auditable and tied to actual violations.
    if decision.revision_instructions:
        summary = summary.strip()
    return RecommendationDraft(
        summary=summary,
        recommendations=recommendations,
        factual_claims=claims,
        citations=citations,
        disclaimers=list(dict.fromkeys(disclaimers)),
    )


def render_recommendation(draft: RecommendationDraft) -> str:
    lines = ["## 家庭保障规划（演示版）", "", draft.summary, "", "### 在售产品候选"]
    if draft.recommendations:
        for item in draft.recommendations:
            price = f"，最低保费{item.min_price:.0f}元" if item.min_price is not None else ""
            lines.append(
                f"- {item.product_name}（{item.product_id}，{item.insurance_type}{price}）："
                f"{item.rationale}"
            )
    else:
        lines.append("- 当前没有可验证的在售产品推荐，需人工确认。")

    lines.extend(["", "### 可核验事实"])
    if draft.factual_claims:
        for claim in draft.factual_claims:
            suffix = f" [{claim.citation_id}]" if claim.citation_id else ""
            lines.append(f"- {claim.text}{suffix}")
    else:
        lines.append("- 暂无可核验条款结论；相关信息不确定，需人工确认。")

    if draft.citations:
        lines.extend(["", "### 引用"])
        for item in draft.citations:
            locator = item.section or (f"第{item.page}页" if item.page else "位置未标注")
            lines.append(f"- [{item.citation_id}] {item.title}，{locator}：{item.excerpt}")

    lines.extend(["", "### 重要声明"])
    lines.extend(f"> {item}" for item in draft.disclaimers)
    return "\n".join(lines)


def _violation(
    code: str,
    message: str,
    *,
    claim_id: str | None = None,
    product_id: str | None = None,
    level: str = "code",
) -> ComplianceViolation:
    return ComplianceViolation(
        code=code,
        message=message,
        claim_id=claim_id,
        product_id=product_id,
        level=level,
    )


def _revision_instructions(
    violations: list[ComplianceViolation],
    unsupported_claims: list[str],
) -> list[str]:
    instructions = [item.message for item in violations]
    if unsupported_claims:
        instructions.append("删除或改写所有无来源支持的事实声明")
    return list(dict.fromkeys(instructions))


def _remove_banned_promises(text: str) -> str:
    cleaned = text
    replacements = {
        "保证赔付": "是否赔付以正式条款与理赔审核为准",
        "保证理赔": "是否理赔以正式条款与审核为准",
        "保证收益": "收益存在不确定性",
        "一定可以投保": "能否投保以核保结果为准",
        "一定承保": "能否承保以核保结果为准",
        "百分之百理赔": "理赔结果以正式审核为准",
        "100%理赔": "理赔结果以正式审核为准",
    }
    for phrase, replacement in replacements.items():
        cleaned = re.sub(re.escape(phrase), replacement, cleaned)
    return cleaned
