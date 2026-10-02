"""Every factual claim must resolve to an approved source boundary."""

from safety.compliance import ComplianceEvaluator
from safety.models import FactualClaim, RecommendationDraft


def test_unknown_business_rule_is_rejected_as_unsupported() -> None:
    draft = RecommendationDraft(
        summary="根据演示规则计算保障缺口。",
        factual_claims=[
            FactualClaim(
                claim_id="RULE-X",
                text="建议保障额度为500万元。",
                source_type="business_rule",
                rule_version="unregistered-v99",
            )
        ],
        disclaimers=["本方案仅供演示，不构成核保结论或正式保险建议。"],
    )

    decision = ComplianceEvaluator(allowed_rule_versions={"v1"}).evaluate(
        draft,
        products=[],
        evidence=[],
        user_question="家庭保障缺口是多少？",
    )

    assert decision.passed is False
    assert "建议保障额度为500万元。" in decision.unsupported_claims
    assert any(item.code == "UNKNOWN_RULE_VERSION" for item in decision.violations)


def test_no_evidence_requires_uncertainty_and_manual_confirmation() -> None:
    draft = RecommendationDraft(
        summary="暂无可验证条款证据，相关条款信息不确定、需人工确认。",
        disclaimers=["本方案仅供演示，不构成核保结论或正式保险建议。"],
    )

    decision = ComplianceEvaluator(allowed_rule_versions={"v1"}).evaluate(
        draft,
        products=[],
        evidence=[],
        user_question="免责条款是什么？",
    )

    assert decision.passed is True
