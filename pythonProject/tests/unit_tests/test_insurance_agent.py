"""Unit tests for insurance_agent tools."""


from insurance_agent.tools import (
    _fallback_regex_extract,
    validate_user_profile,
    _mock_mysql_query,
    _mock_rag_enrich,
)
from insurance_agent.state import UserProfile, REQUIRED_FIELDS


class TestFallbackRegexExtract:
    """Test the regex-based profile extraction fallback."""

    def test_extract_full_profile(self):
        text = "我今年28岁，是程序员，预算5000元，想买重疾险"
        result = _fallback_regex_extract(text)
        assert result["age"] == 28
        assert result["occupation"] == "程序员"
        assert result["budget"] == 5000.0
        assert result["insurance_type"] == "重疾险"

    def test_extract_partial_profile(self):
        text = "我想了解一下保险"
        result = _fallback_regex_extract(text)
        assert result["age"] is None
        assert result["occupation"] is None
        assert result["budget"] is None
        assert result["insurance_type"] is None

    def test_extract_medical_insurance(self):
        text = "30岁，想买医疗险"
        result = _fallback_regex_extract(text)
        assert result["age"] == 30
        assert result["insurance_type"] == "医疗险"

    def test_extract_monthly_budget(self):
        text = "28岁，月预算500"
        result = _fallback_regex_extract(text)
        assert result["budget"] == 6000.0  # 500 * 12

    def test_extract_teacher_occupation(self):
        text = "我是教师，36岁，想买意外险"
        result = _fallback_regex_extract(text)
        assert result["occupation"] == "教师"
        assert result["age"] == 36
        assert result["insurance_type"] == "意外险"


class TestValidateUserProfile:
    """Test profile validation logic."""

    def test_all_fields_present(self):
        profile = {"age": 28, "occupation": "程序员", "budget": 5000, "insurance_type": "重疾险"}
        missing = validate_user_profile(profile)
        assert missing == []

    def test_missing_age(self):
        profile = {"age": None, "occupation": "程序员", "budget": 5000, "insurance_type": "重疾险"}
        missing = validate_user_profile(profile)
        assert "年龄" in missing

    def test_missing_multiple_fields(self):
        profile = {"age": 28, "occupation": None, "budget": None, "insurance_type": None}
        missing = validate_user_profile(profile)
        assert len(missing) == 3
        assert "职业" in missing
        assert "预算" in missing
        assert "保险类型" in missing

    def test_empty_string_treated_as_missing(self):
        profile = {"age": 28, "occupation": "", "budget": 5000, "insurance_type": "重疾险"}
        missing = validate_user_profile(profile)
        assert "职业" in missing


class TestMockMysqlQuery:
    """Test the MySQL mock query with strict condition matching."""

    def test_strict_insurance_type_match(self):
        """Insurance type must match exactly."""
        profile = {"age": 30, "occupation": "程序员", "budget": 10000, "insurance_type": "重疾险"}
        results = _mock_mysql_query(profile)
        # All returned products must be 重疾险
        for p in results:
            assert p["insurance_type"] == "重疾险"

    def test_age_range_match(self):
        """Product age range must cover user's age."""
        profile = {"age": 60, "occupation": "", "budget": 10000, "insurance_type": "重疾险"}
        results = _mock_mysql_query(profile)
        for p in results:
            assert p["min_age"] <= 60 <= p["max_age"]

    def test_budget_filter(self):
        """Products with min_price > budget should be excluded."""
        profile = {"age": 28, "occupation": "", "budget": 2000, "insurance_type": "重疾险"}
        results = _mock_mysql_query(profile)
        for p in results:
            assert p["min_price"] <= 2000

    def test_mismatched_type_returns_empty(self):
        """Non-existent insurance type returns empty list."""
        profile = {"age": 30, "occupation": "程序员", "budget": 5000, "insurance_type": "车险"}
        results = _mock_mysql_query(profile)
        assert results == []

    def test_occupation_filter(self):
        """Products must target the user's occupation."""
        profile = {"age": 28, "occupation": "程序员", "budget": 10000, "insurance_type": "重疾险"}
        results = _mock_mysql_query(profile)
        for p in results:
            assert "程序员" in p["target_occupations"]


class TestMockRagEnrich:
    """Test the RAG enrichment mock."""

    def test_enrich_known_product(self):
        results = _mock_rag_enrich(["CI001"])
        assert len(results) == 1
        assert results[0]["product_id"] == "CI001"
        assert "安心保" in results[0]["rag_content"]

    def test_enrich_unknown_product(self):
        results = _mock_rag_enrich(["UNKNOWN_ID"])
        assert len(results) == 1
        assert results[0]["product_id"] == "UNKNOWN_ID"
        assert "暂无" in results[0]["rag_content"]

    def test_enrich_multiple_products(self):
        results = _mock_rag_enrich(["CI001", "CI002", "MI001"])
        assert len(results) == 3
        ids = {r["product_id"] for r in results}
        assert ids == {"CI001", "CI002", "MI001"}


class TestUserProfileDataclass:
    """Test the UserProfile dataclass."""

    def test_default_values(self):
        profile = UserProfile()
        assert profile.age is None
        assert profile.occupation is None
        assert profile.budget is None
        assert profile.insurance_type is None

    def test_full_construction(self):
        profile = UserProfile(age=28, occupation="程序员", budget=5000.0, insurance_type="重疾险")
        assert profile.age == 28
        assert profile.occupation == "程序员"
        assert profile.budget == 5000.0
        assert profile.insurance_type == "重疾险"


class TestRequiredFields:
    """Test the REQUIRED_FIELDS constant."""

    def test_all_four_fields_required(self):
        assert len(REQUIRED_FIELDS) == 4
        assert "age" in REQUIRED_FIELDS
        assert "occupation" in REQUIRED_FIELDS
        assert "budget" in REQUIRED_FIELDS
        assert "insurance_type" in REQUIRED_FIELDS

    def test_chinese_labels(self):
        assert REQUIRED_FIELDS["age"] == "年龄"
        assert REQUIRED_FIELDS["occupation"] == "职业"
        assert REQUIRED_FIELDS["budget"] == "预算"
        assert REQUIRED_FIELDS["insurance_type"] == "保险类型"
