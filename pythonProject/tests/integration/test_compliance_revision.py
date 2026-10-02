"""Compliance performs one targeted revision and then stops."""

from safety.compliance import SAFE_FALLBACK, ComplianceEvaluator, revise_draft_once
from safety.models import FactualClaim, Recommendation, RecommendationDraft
from tools.product_tools import Product


def _product(name: str = "测试重疾险") -> Product:
    return Product(
        product_id="CI001",
        product_name=name,
        insurance_type="重疾险",
        min_age=18,
        max_age=55,
        min_price=3000,
        max_price=8000,
        target_occupations="全部职业",
        is_active=True,
    )


def _unsafe_draft(product_name: str = "伪造名称") -> RecommendationDraft:
    return RecommendationDraft(
        summary="该产品保证赔付。",
        recommendations=[
            Recommendation(
                product_id="CI001",
                product_name=product_name,
                insurance_type="重疾险",
                min_age=18,
                max_age=55,
                min_price=1,
                max_price=8000,
                rationale="保证赔付。",
            )
        ],
        factual_claims=[
            FactualClaim(
                claim_id="PRODUCT-1",
                text="最低保费为1元。",
                source_type="product_field",
                product_id="CI001",
                field_name="min_price",
                value=1,
            )
        ],
    )


def test_failed_draft_is_revised_once_and_passes() -> None:
    product = _product()
    evaluator = ComplianceEvaluator(allowed_rule_versions={"v1"})
    first = evaluator.evaluate(
        _unsafe_draft(),
        products=[product],
        evidence=[],
        user_question="请推荐重疾险",
    )
    assert first.passed is False

    revised = revise_draft_once(
        _unsafe_draft(),
        first,
        products=[product],
        evidence=[],
        allowed_rule_versions={"v1"},
    )
    second = evaluator.evaluate(
        revised,
        products=[product],
        evidence=[],
        user_question="请推荐重疾险",
        revision_count=1,
    )

    assert second.passed is True
    assert second.revision_count == 1
    assert revised.recommendations[0].min_price == 3000
    assert "保证赔付" not in str(revised.model_dump())


def test_second_failure_stops_at_one_revision_and_uses_safe_fallback() -> None:
    # Even canonical DB data is rejected when it contains a prohibited promise.
    product = _product(name="保证收益险")
    evaluator = ComplianceEvaluator(allowed_rule_versions={"v1"})
    first = evaluator.evaluate(
        _unsafe_draft(),
        products=[product],
        evidence=[],
        user_question="请推荐重疾险",
    )
    revised = revise_draft_once(
        _unsafe_draft(),
        first,
        products=[product],
        evidence=[],
        allowed_rule_versions={"v1"},
    )
    second = evaluator.evaluate(
        revised,
        products=[product],
        evidence=[],
        user_question="请推荐重疾险",
        revision_count=1,
    )
    answer = "正常答案" if second.passed else SAFE_FALLBACK

    assert second.passed is False
    assert second.revision_count == 1
    assert "不确定、需人工确认" in answer
