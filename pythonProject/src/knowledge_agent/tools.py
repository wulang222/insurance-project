"""知识回答Agent — 核心工具函数

工具清单：
1. rewrite_question       — 结合历史对话，用LLM重写完整问题
2. recognize_intent       — 判断问题意图：查DB 还是 查RAG
3. query_db_by_intent     — 根据意图查询数据库（结构化属性查询）
4. search_rag             — 多collection RAG检索（条款/理赔/FAQ）
5. generate_db_answer     — 将DB查询结果喂给LLM生成自然语言回答
6. generate_rag_answer    — 将RAG检索结果喂给LLM生成知识解答

设计原则：
- 不无脑调RAG：先做意图识别，结构化属性走DB精确查询，非结构化知识才走RAG
- 每个函数都有详细中文注解说明其职责和输入输出
"""

from __future__ import annotations

import json
import re
from typing import Any

from harness.errors import DependencyUnavailableError
from insurance_agent.config import (
    create_llm,
    DASHSCOPE_API_KEY,
    MYSQL_CONFIG,
)
from knowledge_agent.config import RAG_TOP_K
from knowledge_agent.prompts import (
    QUERY_REWRITE_SYSTEM,
    QUERY_REWRITE_USER,
    INTENT_RECOGNITION_SYSTEM,
    INTENT_RECOGNITION_USER,
    DB_QUERY_GENERATION_SYSTEM,
    DB_QUERY_GENERATION_USER,
    ANSWER_FROM_DB_SYSTEM,
    ANSWER_FROM_DB_USER,
    ANSWER_FROM_RAG_SYSTEM,
    ANSWER_FROM_RAG_USER,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 工具1: 问题重写
# ═══════════════════════════════════════════════════════════════════════════════
# 场景：用户在对话中追问"它的等待期是多久？"，需要结合上文才能知道"它"指什么
# 输入：对话历史文本 + 用户原始问题
# 输出：语义完整的独立问题
# 机制：调用LLM进行指代消解和语义补全，LLM不可用时返回原问题

def rewrite_question(history: str, question: str) -> str:
    """结合对话历史，将用户的简短追问重写为语义完整的独立问题。

    例如：
        历史: "用户: 有什么重疾险推荐？\\n助手: 推荐安心保·重疾险..."
        问题: "它多少钱？"
        重写后: "安心保·重疾险（标准版）多少钱？"

    Args:
        history: 格式化的对话历史文本
        question: 用户当前输入的原始问题

    Returns:
        重写后的完整问题；LLM不可用时返回原问题
    """
    # 没有历史或没有API key时，直接返回原问题（无法做指代消解）
    if not history.strip() or not DASHSCOPE_API_KEY:
        return question

    try:
        llm = create_llm(temperature=0)
        prompt = QUERY_REWRITE_USER.format(history=history, question=question)
        messages = [
            {"role": "system", "content": QUERY_REWRITE_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        response = llm.invoke(messages)
        rewritten = response.content.strip() if hasattr(response, "content") else str(response).strip()
        # 防御：如果LLM返回空，回退到原问题
        return rewritten if rewritten else question
    except Exception:
        # LLM调用失败时返回原问题，保证流程不中断
        return question


# ═══════════════════════════════════════════════════════════════════════════════
# 工具2: 意图识别
# ═══════════════════════════════════════════════════════════════════════════════
# 判断用户问题是查数据库（结构化属性）还是查知识库（非结构化知识）
# 输出："db" 或 "rag"
# 核心逻辑：LLM判断 + 关键词兜底，避免无脑调RAG

def recognize_intent(question: str) -> str:
    """判断用户问题的意图类型：'db' (数据库查询) 或 'rag' (知识库检索)

    数据库适用：产品属性、年龄/职业限制、保费、等待期等结构化数值
    知识库适用：条款解释、理赔规则、免责说明、案例分析等非结构化知识

    采用双重判断机制：
    1. 先用LLM做语义意图识别（准确但依赖网络）
    2. LLM不可用时用关键词正则兜底（快速但粗糙）
    """
    # ── 优先：LLM语义意图识别 ──
    if DASHSCOPE_API_KEY:
        try:
            llm = create_llm(temperature=0)
            prompt = INTENT_RECOGNITION_USER.format(question=question)
            messages = [
                {"role": "system", "content": INTENT_RECOGNITION_SYSTEM},
                {"role": "user", "content": prompt},
            ]
            response = llm.invoke(messages)
            raw = response.content.strip().lower() if hasattr(response, "content") else str(response).strip().lower()
            # 提取 "db" 或 "rag"
            if "db" in raw:
                return "db"
            if "rag" in raw:
                return "rag"
        except Exception:
            pass  # LLM失败，走关键词兜底

    # ── 兜底：关键词正则判断 ──
    return _fallback_intent_recognition(question)


def _fallback_intent_recognition(question: str) -> str:
    """用关键词匹配做意图识别的兜底方案。

    匹配逻辑：
    - 包含产品属性关键词（年龄/职业/保费/等待期等） → db
    - 包含知识型关键词（条款/理赔/案例/是什么等） → rag
    - 默认走rag（更安全，知识库覆盖面更广）
    """
    # DB 特征词：询问"有多少/多少钱/多大/什么产品"等可量化属性
    db_keywords = [
        "年龄", "岁", "职业", "保费", "多少钱", "价格", "价格范围",
        "等待期", "犹豫期", "多少天", "缴费", "保额", "最高", "最低",
        "以下", "以上", "以内", "不超过",  # 价格/数值范围词
        "有哪些", "有什么产品", "推荐", "哪个好", "什么产品",
        "产品列表", "所有", "全部", "适合.*职业", "职业.*限制",
    ]
    # RAG 特征词：询问"是什么意思/怎么赔/什么情况"等解释性问题
    rag_keywords = [
        "是什么意思", "什么意思", "怎么赔", "如何理赔", "理赔流程",
        "条款", "免责", "不赔", "案例", "什么情况", "解释",
        "什么是", "定义", "含义", "区别", "对比", "现金价值",
        "豁免", "轻症", "重症", "保障范围", "覆盖",
    ]

    # 检查DB关键词
    for kw in db_keywords:
        if re.search(kw, question):
            return "db"
    # 检查RAG关键词
    for kw in rag_keywords:
        if re.search(kw, question):
            return "rag"
    # 默认走RAG（更安全）
    return "rag"


# ═══════════════════════════════════════════════════════════════════════════════
# 工具3: 数据库结构化查询
# ═══════════════════════════════════════════════════════════════════════════════
# 对于"db"意图的问题，先让LLM将问题转为查询参数JSON，再执行SQL
# 这样比硬编码规则更灵活，用户可以自然语言提问，LLM负责解析

def query_db_by_intent(question: str) -> list[dict]:
    """根据用户问题，用LLM生成查询参数 → 执行MySQL精确查询。

    两步走：
    Step 1: LLM解析问题，输出结构化查询参数JSON
    Step 2: 代码根据JSON构建SQL并执行（防止SQL注入）

    支持两种查询模式：
    - filter: 有条件筛选（如"重疾险中适合30岁程序员的有哪些"）
    - list_all: 无条件列出所有产品（如"有哪些保险产品"）
    """
    # ══ Step 1: LLM生成查询参数 ══
    query_params = _generate_db_query_params(question)

    # ══ Step 2: 执行SQL ══
    # 业务数据必须来自真实 MySQL，依赖故障不得伪装成空结果。
    try:
        return _execute_mysql_query(query_params)
    except Exception as exc:
        raise DependencyUnavailableError(
            "MySQL is unavailable",
            details={"dependency": "mysql"},
            retryable=True,
        ) from exc


def _generate_db_query_params(question: str) -> dict:
    """调用LLM将自然语言问题转为结构化查询参数JSON。

    Args:
        question: 用户重写后的完整问题

    Returns:
        查询参数字典，格式：
        {
            "query_type": "filter",
            "filters": {"insurance_type": "重疾险", "age": 30, ...}
        }
    """
    if not DASHSCOPE_API_KEY:
        return {"query_type": "filter", "filters": _keyword_extract_filters(question)}

    try:
        llm = create_llm(temperature=0)
        prompt = DB_QUERY_GENERATION_USER.format(question=question)
        messages = [
            {"role": "system", "content": DB_QUERY_GENERATION_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        # 清洗：去除可能的 markdown 代码块标记
        content = content.strip()
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            content = match.group(0)
        return json.loads(content)
    except (json.JSONDecodeError, Exception):
        # LLM输出解析失败，用关键词兜底
        return {"query_type": "filter", "filters": _keyword_extract_filters(question)}


def _keyword_extract_filters(question: str) -> dict:
    """兜底方案：用正则从问题中提取查询条件。

    当LLM不可用或输出解析失败时，直接正则匹配关键词构建查询。
    """
    filters: dict[str, Any] = {}

    # 险种类型匹配
    insurance_types = ["重疾险", "医疗险", "意外险", "寿险", "年金险"]
    for it in insurance_types:
        if it in question:
            filters["insurance_type"] = it
            break

    # 年龄匹配（如"30岁""适合30岁的"）
    age_match = re.search(r'(\d{1,3})\s*岁', question)
    if age_match:
        filters["age"] = int(age_match.group(1))

    # 保费上限匹配（如"5000以下""预算5000"）
    price_match = re.search(r'(?:预算|以下|以内|不超过).*?(\d{2,6})', question)
    if price_match:
        filters["max_price_limit"] = int(price_match.group(1))

    # 产品名模糊匹配（如"安心保"）
    name_match = re.search(r'(?:关于|了解)?(.+?)(?:的|这款|这个|产品)', question)
    if name_match:
        product_name = name_match.group(1).strip()
        if len(product_name) >= 2 and product_name not in insurance_types:
            filters["product_name_like"] = product_name

    return filters


def _execute_mysql_query(query_params: dict) -> list[dict]:
    """根据查询参数执行MySQL查询。

    参数由LLM生成，但SQL由代码拼接，使用参数化查询防止SQL注入。
    """
    import pymysql

    conn = pymysql.connect(
        host=MYSQL_CONFIG["host"],
        port=MYSQL_CONFIG["port"],
        user=MYSQL_CONFIG["user"],
        password=MYSQL_CONFIG["password"],
        database=MYSQL_CONFIG["database"],
        charset="utf8mb4",
        connect_timeout=5,
    )
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        filters = query_params.get("filters", {})

        # 无条件列出所有产品（限制20条）
        if query_params.get("query_type") == "list_all" or not filters:
            sql = (
                "SELECT product_id, product_name, insurance_type, "
                "min_age, max_age, min_price, max_price, "
                "target_occupations, description "
                "FROM insurance_products WHERE is_active=1 "
                "ORDER BY insurance_type, min_price LIMIT 20"
            )
            cursor.execute(sql)
            rows = cursor.fetchall()
            return _format_decimal_fields(rows)

        # 有条件筛选
        conditions = ["is_active=1"]
        params: list[Any] = []

        # 险种精确匹配
        if "insurance_type" in filters:
            conditions.append("insurance_type = %s")
            params.append(filters["insurance_type"])

        # 年龄范围匹配（查询覆盖该年龄的产品）
        if "age" in filters:
            conditions.append("min_age <= %s AND max_age >= %s")
            params.extend([filters["age"], filters["age"]])

        # 保费上限
        if "max_price_limit" in filters:
            conditions.append("min_price <= %s")
            params.append(filters["max_price_limit"])

        # 产品名模糊匹配
        if "product_name_like" in filters:
            conditions.append("product_name LIKE %s")
            params.append(f"%{filters['product_name_like']}%")

        sql = (
            "SELECT product_id, product_name, insurance_type, "
            "min_age, max_age, min_price, max_price, "
            "target_occupations, description "
            f"FROM insurance_products WHERE {' AND '.join(conditions)} "
            "ORDER BY min_price ASC LIMIT 20"
        )
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return _format_decimal_fields(rows)
    finally:
        cursor.close()
        conn.close()


def _format_decimal_fields(rows: list[dict]) -> list[dict]:
    """将DECIMAL字段转为float，方便序列化。"""
    for row in rows:
        for key in ("min_price", "max_price"):
            if row.get(key) is not None:
                row[key] = float(row[key])
    return rows


def _mock_db_query(query_params: dict) -> list[dict]:
    """数据库不可用时的mock查询数据（与SQL初始化数据一致）。"""
    # 复用 insurance_agent 中的 mock 数据
    from insurance_agent.tools import _mock_mysql_query

    filters = query_params.get("filters", {})
    # 构造兼容 profile 格式；list_all 不传 insurance_type，mock 会默认"重疾险"
    profile = {
        "insurance_type": filters.get("insurance_type"),
        "age": filters.get("age", 30),
        "budget": filters.get("max_price_limit", 999999),
        "occupation": "",
    }
    products = _mock_mysql_query(profile)

    # 如果有 product_name_like，做客户端过滤
    name_like = filters.get("product_name_like")
    if name_like:
        products = [p for p in products if name_like in p.get("product_name", "")]

    return products


# ═══════════════════════════════════════════════════════════════════════════════
# 工具4: Milvus RAG检索
# ═══════════════════════════════════════════════════════════════════════════════
# 从 Milvus 向量库中检索与用户问题相关的保险知识内容
# 与 insurance_agent 共用同一 Milvus 集合（内含产品信息、条款、理赔案例等）

def search_rag(question: str) -> list[dict]:
    """从 Milvus 知识库检索与用户问题相关的内容。

    检索策略：
    - 单次检索取 RAG_TOP_K * 2 条（因为只有一个 collection，适当多取）
    - 根据相似度分数排序，确保返回最相关的内容

    Args:
        question: 用户重写后的完整问题

    Returns:
        文档列表，每个元素 {"content": str, "source": str, "score": float}
    """
    from shared.milvus_utils import (
        is_milvus_available,
        get_embedding_function,
        milvus_search,
    )

    if not is_milvus_available():
        raise DependencyUnavailableError(
            "Milvus or its embedding provider is unavailable",
            details={"dependency": "milvus"},
            retryable=True,
        )

    embed_func = get_embedding_function()
    if embed_func is None:
        raise DependencyUnavailableError(
            "Embedding provider is unavailable",
            details={"dependency": "embedding"},
            retryable=True,
        )

    try:
        hits = milvus_search(question, top_k=RAG_TOP_K * 2)
    except Exception as exc:
        raise DependencyUnavailableError(
            "Milvus search failed",
            details={"dependency": "milvus"},
            retryable=True,
        ) from exc

    if not hits:
        return []

    all_docs: list[dict] = []
    seen_contents = set()

    for hit in sorted(hits, key=lambda h: h["score"], reverse=True):
        content = hit.get("text", "").strip()
        if not content or content in seen_contents:
            continue
        seen_contents.add(content)
        source = hit.get("file_path", "").replace("\\", "/").split("/")[-1]
        all_docs.append({
            "content": content,
            "source": source,
            "score": hit.get("score", 0),
        })

    return all_docs


def _mock_rag_search(question: str) -> list[dict]:
    """RAG不可用时的mock知识库数据。

    覆盖常见的保险知识问答，确保即使没有真实向量库也能演示效果。
    """
    # 预置知识条目（模拟向量库中存储的内容）
    knowledge_entries = [
        {
            "content": (
                "【等待期】等待期是指保险合同生效后，被保险人发生保险事故，"
                "保险公司不承担赔付责任的一段时间。重疾险等待期通常为90天或180天，"
                "医疗险等待期通常为30天。意外险一般无等待期。"
                "等待期的设置是为了防止带病投保。"
            ),
            "collection": "terms",
        },
        {
            "content": (
                "【犹豫期】犹豫期是指投保人签收保单后，可以无条件退保的一段时间。"
                "长期保险的犹豫期通常为15天，短期保险可能没有犹豫期。"
                "在犹豫期内退保，保险公司扣除不超过10元的工本费后全额退还保费。"
            ),
            "collection": "terms",
        },
        {
            "content": (
                "【免责条款】以下情况保险公司不承担赔付责任：\\n"
                "1. 投保人故意杀害、伤害被保险人\\n"
                "2. 被保险人故意犯罪或抗拒依法采取的刑事强制措施\\n"
                "3. 被保险人酒后驾驶、无证驾驶\\n"
                "4. 战争、军事冲突、暴乱或武装叛乱\\n"
                "5. 核爆炸、核辐射或核污染\\n"
                "6. 被保险人吸毒或注射毒品\\n"
                "7. 被保险人感染艾滋病病毒（特定产品除外）"
            ),
            "collection": "terms",
        },
        {
            "content": (
                "【轻症豁免】轻症豁免是指在缴费期内，如果被保险人确诊合同约定的轻症疾病，"
                "后续保费无需再缴纳，但保险合同继续有效。这是重疾险中非常重要的保障条款，"
                "建议选择包含轻症豁免的产品。"
            ),
            "collection": "terms",
        },
        {
            "content": (
                "【理赔流程】保险理赔一般流程：\\n"
                "1. 出险后及时报案（通常要求48小时内）\\n"
                "2. 准备理赔材料（病历、诊断证明、费用清单、身份证明等）\\n"
                "3. 提交理赔申请\\n"
                "4. 保险公司审核（通常5-15个工作日）\\n"
                "5. 赔付到账\\n"
                "建议出险后第一时间联系保险顾问，协助准备材料。"
            ),
            "collection": "claims",
        },
        {
            "content": (
                "【理赔案例】张先生，30岁，程序员，2024年3月投保'安心保·重疾险（标准版）'，"
                "年缴保费4500元，保额50万元。2025年1月确诊甲状腺癌（属合同约定的重疾），"
                "提交理赔申请后10个工作日内获得50万元赔付，后续保费豁免。"
                "该产品诊断为恶性肿瘤即可赔付，无需等待治疗结束。"
            ),
            "collection": "claims",
        },
        {
            "content": (
                "【投保建议-重疾险】\\n"
                "1. 保额建议为年收入的3-5倍，至少30万起步\\n"
                "2. 选择包含轻症、中症责任的产品\\n"
                "3. 优先选择含轻症豁免的产品\\n"
                "4. 年轻人建议选定期重疾险（保费更低），中年人建议选终身重疾险\\n"
                "5. 重疾险越早买越好，年龄越小保费越低且健康状况好核保容易通过"
            ),
            "collection": "faq",
        },
        {
            "content": (
                "【投保建议-医疗险】\\n"
                "1. 医疗险和重疾险不冲突，建议搭配购买\\n"
                "2. 关注免赔额和赔付比例\\n"
                "3. 确认是否包含自费药和进口药报销\\n"
                "4. 优先选择保证续保的产品\\n"
                "5. 百万医疗险保费低、保额高，适合作为基础保障"
            ),
            "collection": "faq",
        },
    ]

    # 简单关键词匹配选择最相关的条目
    results = []
    for entry in knowledge_entries:
        # 用简单的词汇重叠做相关性判断
        question_words = set(question)
        content_words = set(entry["content"])
        overlap = len(question_words & content_words)
        if overlap > 5:  # 阈值筛选
            results.append(entry)

    # 如果关键词匹配不到，返回所有条目
    return results if results else knowledge_entries[:5]


# ═══════════════════════════════════════════════════════════════════════════════
# 工具5: 生成最终知识解答
# ═══════════════════════════════════════════════════════════════════════════════
# 将DB或RAG的查询结果喂给LLM，生成自然语言回答
# 两个函数分别处理DB和RAG两种结果格式

def generate_db_answer(question: str, db_results: list[dict]) -> str:
    """将数据库查询的结构化数据转为自然语言回答。

    LLM负责：把表格数据翻译成通俗易懂的文字描述，适当组织层次结构。
    LLM不可用时：用简单模板兜底。
    """
    if not db_results:
        return (
            "根据您的查询条件，暂未找到匹配的保险产品。\n\n"
            "建议您：\n"
            "1. 尝试放宽查询条件（如不限制具体险种）\n"
            "2. 联系保险顾问获取更详细的产品信息"
        )

    # 格式化DB结果为可读文本
    db_text = _format_db_results_for_llm(db_results)

    if not DASHSCOPE_API_KEY:
        return _template_db_answer(question, db_results)

    try:
        llm = create_llm(temperature=0.3)
        prompt = ANSWER_FROM_DB_USER.format(question=question, db_results=db_text)
        messages = [
            {"role": "system", "content": ANSWER_FROM_DB_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        response = llm.invoke(messages)
        return response.content if hasattr(response, "content") else str(response)
    except Exception:
        return _template_db_answer(question, db_results)


def generate_rag_answer(question: str, rag_docs: list[dict]) -> str:
    """将RAG检索的知识片段整理归纳为结构化回答。

    LLM负责：从多段检索结果中提取关键信息，组织为条理清晰的回答。
    LLM不可用时：直接拼接知识片段。
    """
    if not rag_docs:
        return (
            "抱歉，当前知识库中暂未找到与您问题直接相关的内容。\n\n"
            "建议您：\n"
            "1. 换个方式重新提问\n"
            "2. 联系人工客服获取更详细的解答"
        )

    # 格式化RAG结果为带来源标记的文本
    rag_text = _format_rag_results_for_llm(rag_docs)

    if not DASHSCOPE_API_KEY:
        return _template_rag_answer(question, rag_docs)

    try:
        llm = create_llm(temperature=0.3)
        prompt = ANSWER_FROM_RAG_USER.format(question=question, rag_context=rag_text)
        messages = [
            {"role": "system", "content": ANSWER_FROM_RAG_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        response = llm.invoke(messages)
        return response.content if hasattr(response, "content") else str(response)
    except Exception:
        return _template_rag_answer(question, rag_docs)


# ── 辅助函数 ──────────────────────────────────────────────

def _format_db_results_for_llm(db_results: list[dict]) -> str:
    """将数据库查询结果格式化为LLM易于理解的文本。"""
    lines = []
    for i, row in enumerate(db_results, 1):
        lines.append(
            f"{i}. 【{row.get('product_id', '')}】{row.get('product_name', '')}\n"
            f"   险种: {row.get('insurance_type', '')}  |  "
            f"投保年龄: {row.get('min_age', '')}-{row.get('max_age', '')}岁  |  "
            f"保费: {row.get('min_price', '')}-{row.get('max_price', '')}元/年\n"
            f"   适合职业: {row.get('target_occupations', '')}\n"
            f"   描述: {row.get('description', '')}"
        )
    return "\n".join(lines)


def _format_rag_results_for_llm(rag_docs: list[dict]) -> str:
    """将RAG检索结果格式化为带来源信息的文本。"""
    parts = []
    for i, doc in enumerate(rag_docs, 1):
        source = doc.get("source") or doc.get("collection", "")
        score = doc.get("score", 0)
        source_tag = f" [{source}] (相关度: {score:.2f})" if source and score else f" [{source}]" if source else ""
        parts.append(f"【资料{i}】{source_tag}\n{doc['content']}")
    return "\n\n---\n\n".join(parts)


def _template_db_answer(question: str, db_results: list[dict]) -> str:
    """LLM不可用时的数据库回答兜底模板。"""
    lines = [
        f"根据您的问题「{question}」，查询到以下{len(db_results)}款产品：",
        "",
    ]
    for i, row in enumerate(db_results, 1):
        lines.append(
            f"### {i}. {row.get('product_name', '未知产品')}\n"
            f"- 产品编号: {row.get('product_id', '')}\n"
            f"- 险种: {row.get('insurance_type', '')}\n"
            f"- 投保年龄: {row.get('min_age', '')}-{row.get('max_age', '')}岁\n"
            f"- 保费范围: {row.get('min_price', '')}-{row.get('max_price', '')}元/年\n"
            f"- 适合职业: {row.get('target_occupations', '')}\n"
            f"- 产品描述: {row.get('description', '')}\n"
        )
    return "\n".join(lines)


def _template_rag_answer(question: str, rag_docs: list[dict]) -> str:
    """LLM不可用时的RAG回答兜底模板。"""
    lines = [f"关于您的问题「{question}」，以下是知识库中的相关内容：", ""]
    for i, doc in enumerate(rag_docs, 1):
        source = doc.get("source", doc.get("collection", ""))
        lines.append(f"### {i}. 来源: {source}\n{doc['content']}\n")
    lines.append("\n---\n> 以上内容来自保险知识库，仅供参考。如有疑问请联系保险顾问。")
    return "\n".join(lines)
