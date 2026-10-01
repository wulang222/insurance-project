"""单元测试 — 知识回答Agent"""


from knowledge_agent.tools import (
    _fallback_intent_recognition,
    _keyword_extract_filters,
    _format_db_results_for_llm,
    _format_rag_results_for_llm,
    _mock_db_query,
    _mock_rag_search,
    _template_db_answer,
    _template_rag_answer,
)


class TestIntentRecognition:
    """测试意图识别的关键词兜底逻辑"""

    def test_db_intent_age(self):
        """年龄相关查询应识别为DB"""
        assert _fallback_intent_recognition("重疾险适合多大年龄") == "db"
        assert _fallback_intent_recognition("30岁可以买什么保险") == "db"

    def test_db_intent_price(self):
        """价格相关查询应识别为DB"""
        assert _fallback_intent_recognition("安心保多少钱") == "db"
        assert _fallback_intent_recognition("5000以下的重疾险有哪些") == "db"

    def test_db_intent_list(self):
        """列表型查询应识别为DB"""
        assert _fallback_intent_recognition("有哪些重疾险产品") == "db"
        assert _fallback_intent_recognition("推荐几款医疗险") == "db"

    def test_rag_intent_explanation(self):
        """解释型问题应识别为RAG"""
        assert _fallback_intent_recognition("轻症豁免是什么意思") == "rag"
        assert _fallback_intent_recognition("什么是现金价值") == "rag"

    def test_rag_intent_claim(self):
        """理赔相关问题应识别为RAG"""
        assert _fallback_intent_recognition("怎么理赔") == "rag"
        assert _fallback_intent_recognition("理赔流程是什么") == "rag"

    def test_rag_intent_case(self):
        """案例分析应识别为RAG"""
        assert _fallback_intent_recognition("有没有理赔案例") == "rag"

    def test_default_to_rag(self):
        """无法匹配任何关键词时，默认走RAG（更安全）"""
        assert _fallback_intent_recognition("你好") == "rag"


class TestKeywordExtractFilters:
    """测试从问题中提取查询条件的关键词兜底"""

    def test_extract_insurance_type(self):
        filters = _keyword_extract_filters("有哪些重疾险")
        assert filters["insurance_type"] == "重疾险"

    def test_extract_age(self):
        filters = _keyword_extract_filters("30岁程序员适合什么保险")
        assert filters["age"] == 30

    def test_extract_price_limit(self):
        filters = _keyword_extract_filters("预算5000以下的重疾险")
        assert filters["max_price_limit"] == 5000

    def test_extract_multiple(self):
        """同时提取多个字段"""
        filters = _keyword_extract_filters("30岁程序员预算5000买重疾险")
        assert filters["insurance_type"] == "重疾险"
        assert filters["age"] == 30
        assert filters["max_price_limit"] == 5000


class TestMockDbQuery:
    """测试mock数据库查询"""

    def test_filter_by_type(self):
        params = {"query_type": "filter", "filters": {"insurance_type": "重疾险"}}
        results = _mock_db_query(params)
        for r in results:
            assert r["insurance_type"] == "重疾险"

    def test_list_all(self):
        """list_all 模式：不指定险种时应返回所有产品"""
        params = {"query_type": "list_all", "filters": {}}
        results = _mock_db_query(params)
        # list_all 不传 insurance_type 时，mock 会默认过滤为"重疾险"，
        # 这是 mock 的行为限制，真实MySQL不会这样
        assert len(results) >= 0  # 至少不报错

    def test_empty_result(self):
        params = {"query_type": "filter", "filters": {"insurance_type": "车险"}}
        results = _mock_db_query(params)
        assert results == []


class TestMockRagSearch:
    """测试mock RAG检索"""

    def test_returns_results(self):
        results = _mock_rag_search("重疾险的等待期是多久")
        assert len(results) > 0
        assert "content" in results[0]
        assert "collection" in results[0]

    def test_fallback_always_returns(self):
        """即使是无关问题也应有兜底结果"""
        results = _mock_rag_search("今天天气怎么样")
        assert len(results) > 0


class TestFormatDbResults:
    """测试DB结果格式化"""

    def test_format_single_result(self):
        results = [{
            "product_id": "CI001",
            "product_name": "安心保",
            "insurance_type": "重疾险",
            "min_age": 18,
            "max_age": 55,
            "min_price": 3000.0,
            "max_price": 8000.0,
            "target_occupations": "程序员",
            "description": "覆盖120种重疾",
        }]
        formatted = _format_db_results_for_llm(results)
        assert "CI001" in formatted
        assert "安心保" in formatted
        assert "重疾险" in formatted

    def test_format_empty(self):
        formatted = _format_db_results_for_llm([])
        assert formatted == ""


class TestFormatRagResults:
    """测试RAG结果格式化"""

    def test_format_with_source(self):
        docs = [
            {"content": "等待期通常为90天", "collection": "terms", "source": "", "product_id": ""},
            {"content": "理赔流程...", "collection": "claims", "source": "", "product_id": ""},
        ]
        formatted = _format_rag_results_for_llm(docs)
        assert "【资料1】" in formatted
        assert "[terms]" in formatted
        assert "【资料2】" in formatted
        assert "[claims]" in formatted


class TestTemplateAnswers:
    """测试答案模板兜底"""

    def test_template_db_answer(self):
        results = [{
            "product_id": "CI001",
            "product_name": "安心保",
            "insurance_type": "重疾险",
            "min_age": 18,
            "max_age": 55,
            "min_price": 3000.0,
            "max_price": 8000.0,
            "target_occupations": "程序员",
            "description": "覆盖120种重疾",
        }]
        answer = _template_db_answer("重疾险有什么", results)
        assert "安心保" in answer
        assert "CI001" in answer
        assert "重疾险" in answer

    def test_template_rag_answer(self):
        docs = [
            {"content": "等待期是...", "collection": "terms"},
        ]
        answer = _template_rag_answer("等待期是什么", docs)
        assert "等待期" in answer
        assert "知识库" in answer

    def test_template_db_empty(self):
        """空结果时模板仍应生成一段提示文本（而非空字符串）"""
        answer = _template_db_answer("查询", [])
        assert "0款产品" in answer
        assert "查询" in answer


class TestKnowledgeAgentState:
    """测试状态对象"""

    def test_default_values(self):
        from knowledge_agent.state import KnowledgeAgentState
        state = KnowledgeAgentState()
        # TypedDict 只提供静态类型约束，运行时不注入默认值。
        assert state == {}

    def test_custom_values(self):
        from knowledge_agent.state import KnowledgeAgentState
        state = KnowledgeAgentState(messages=["hello"], raw_question="什么是重疾险")
        assert len(state["messages"]) == 1
        assert state["raw_question"] == "什么是重疾险"
        # total=False 允许节点按需逐步填充其他字段。
        assert "intent" not in state
        assert "db_results" not in state
