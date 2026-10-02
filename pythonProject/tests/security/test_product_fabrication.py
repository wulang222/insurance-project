"""Product recommendations and product-linked citations stay grounded."""

from safety.compliance import ComplianceEvaluator
from safety.evidence import citation_from_evidence
from safety.models import FactualClaim, Recommendation, RecommendationDraft
from tools.policy_tools import Evidence
from tools.product_tools import Product


PRODUCT = Product(
    product_id="CI001",
    product_name="测试重疾险",
    insurance_type="重疾险",
    min_age=18,
    max_age=55,
    min_price=3000,
    max_price=8000,
    target_occupations="全部职业",
    is_active=True,
)


def _recommendation(**updates) -> Recommendation:
    values = {
        "product_id": PRODUCT.product_id,
        "product_name": PRODUCT.product_name,
        "insurance_type": PRODUCT.insurance_type,
        "min_age": PRODUCT.min_age,
        "max_age": PRODUCT.max_age,
        "min_price": PRODUCT.min_price,
        "max_price": PRODUCT.max_price,
        "rationale": "来自当前在售产品查询。",
    }
    values.update(updates)
    return Recommendation(**values)


def _draft(recommendation: Recommendation, **updates) -> RecommendationDraft:
    values = {
        "summary": "根据当前在售产品生成候选。",
        "recommendations": [recommendation],
        "disclaimers": ["本方案仅供演示，不构成核保结论或正式保险建议。"],
    }
    values.update(updates)
    return RecommendationDraft(**values)


def _evaluate(draft: RecommendationDraft, evidence: list[Evidence] | None = None):
    return ComplianceEvaluator(allowed_rule_versions={"v1"}).evaluate(
        draft,
        products=[PRODUCT],
        evidence=evidence or [],
        user_question="请推荐重疾险",
    )


def test_nonexistent_product_is_rejected() -> None:
    decision = _evaluate(_draft(_recommendation(product_id="FAKE-999")))

    assert decision.passed is False
    assert any(item.code == "PRODUCT_NOT_ACTIVE" for item in decision.violations)


def test_modified_database_premium_is_rejected() -> None:
    decision = _evaluate(_draft(_recommendation(min_price=1)))

    assert decision.passed is False
    assert any(item.code == "PRODUCT_FIELD_MISMATCH" for item in decision.violations)


def test_citation_from_another_product_is_rejected() -> None:
    evidence = Evidence(
        content="产品A的等待期为90天。",
        score=0.95,
        document_id="DOC-A",
        product_id="CI-OTHER",
        document_type="policy_terms",
        title="产品A条款",
        section="等待期",
        page=2,
        effective_date="2026-01-01",
        version="v1",
        source_path="fixture://product-a.pdf",
        checksum="doc-a-v1",
    )
    citation = citation_from_evidence(evidence)
    draft = _draft(
        _recommendation(),
        factual_claims=[
            FactualClaim(
                claim_id="CLAIM-1",
                text="测试重疾险等待期为90天。",
                source_type="citation",
                product_id="CI001",
                citation_id=citation.citation_id,
            )
        ],
        citations=[citation],
    )

    decision = _evaluate(draft, [evidence])

    assert decision.passed is False
    assert any(item.code == "CITATION_PRODUCT_MISMATCH" for item in decision.violations)
