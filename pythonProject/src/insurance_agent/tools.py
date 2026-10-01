"""Tools for the insurance recommendation agent."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.tools import tool

from insurance_agent.config import (
    MYSQL_CONFIG,
    DASHSCOPE_API_KEY,
    RAG_TOP_K,
    create_llm,
)
from insurance_agent.state import REQUIRED_FIELDS
from insurance_agent.prompts import (
    EXTRACT_PROFILE_SYSTEM_PROMPT,
    EXTRACT_PROFILE_USER_PROMPT,
    HISTORICAL_PROFILE_CONTEXT,
)
from shared.milvus_utils import (
    get_embedding_function,
    is_milvus_available,
    milvus_search,
)


# ---------------------------------------------------------------------------
# Tool 1: Extract user profile from conversation via LLM
# ---------------------------------------------------------------------------

@tool
def extract_user_profile(conversation: str, stored_profile: str = "") -> dict:
    """Extract structured user profile (age, occupation, budget, insurance_type)
    from the conversation history using LLM.

    Args:
        conversation: The full conversation text between user and AI.

    Returns:
        A dict like {"age": 28, "occupation": "程序员", "budget": 5000, "insurance_type": "重疾险"}
        Fields that cannot be extracted are set to null.
    """
    if not DASHSCOPE_API_KEY:
        return _fallback_regex_extract(conversation)

    try:
        llm = create_llm(temperature=0)
    except ImportError:
        return _fallback_regex_extract(conversation)

    prompt = EXTRACT_PROFILE_USER_PROMPT.format(conversation=conversation)
    messages = [
        {"role": "system", "content": EXTRACT_PROFILE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    if stored_profile:
        messages.insert(1, {"role": "user", "content": HISTORICAL_PROFILE_CONTEXT.format(stored_profile_json=stored_profile)})

    try:
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        content = _clean_json_content(content)
        return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return _fallback_regex_extract(conversation)


def _clean_json_content(content: str) -> str:
    """Strip markdown code fences and extract the JSON substring."""
    content = content.strip()
    match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
    if match:
        return match.group(0)
    return content


def _fallback_regex_extract(conversation: str) -> dict:
    """Simple regex-based fallback when LLM is unavailable."""
    result: dict[str, Any] = {"age": None, "occupation": None, "budget": None, "insurance_type": None}

    age_match = re.search(r'(\d{1,3})\s*[岁歲]', conversation)
    if age_match:
        result["age"] = int(age_match.group(1))

    budget_match = re.search(r'(?:预算|保费|费用|每年|月).*?(\d{2,6})', conversation)
    if budget_match:
        budget = int(budget_match.group(1))
        if "月" in conversation:
            budget *= 12
        result["budget"] = float(budget)

    occ_patterns = ["程序员", "教师", "医生", "护士", "律师", "工程师", "设计师", "销售", "会计", "公务员"]
    for occ in occ_patterns:
        if occ in conversation:
            result["occupation"] = occ
            break

    insurance_types = ["重疾险", "医疗险", "意外险", "寿险", "年金险", "重大疾病", "百万医疗"]
    mapping = {"重大疾病": "重疾险", "百万医疗": "医疗险"}
    for ins_type in insurance_types:
        if ins_type in conversation:
            result["insurance_type"] = mapping.get(ins_type, ins_type)
            break

    return result


# ---------------------------------------------------------------------------
# Tool 2: MySQL strict condition query
# ---------------------------------------------------------------------------

@tool
def query_insurance_products_mysql(profile_json: str) -> list[dict]:
    """Query insurance products from MySQL with strict condition matching.

    This performs exact/filtered queries, NOT similarity search, to ensure
    only products that genuinely match the user's constraints are returned.

    Args:
        profile_json: JSON string of UserProfile with age, occupation, budget, insurance_type.

    Returns:
        List of matching product dicts.
    """
    profile = json.loads(profile_json) if isinstance(profile_json, str) else profile_json

    try:
        import pymysql
    except ImportError:
        return []

    try:
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
    except Exception:
        return []

    try:
        conditions = []
        params: list[Any] = []

        # insurance_type — exact match
        if profile.get("insurance_type"):
            conditions.append("insurance_type = %s")
            params.append(profile["insurance_type"])

        # age range match
        if profile.get("age"):
            conditions.append("min_age <= %s AND max_age >= %s")
            params.extend([profile["age"], profile["age"]])

        # budget range match (budget should fall within product price range)
        if profile.get("budget"):
            conditions.append("min_price <= %s")
            params.append(profile["budget"])

        # occupation — LIKE match
        if profile.get("occupation"):
            conditions.append("target_occupations LIKE %s")
            params.append(f"%{profile['occupation']}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = (
            "SELECT product_id, product_name, insurance_type, min_age, max_age, "
            "       min_price, max_price, target_occupations, description "
            f"FROM insurance_products WHERE {where_clause} "
            "ORDER BY min_price ASC LIMIT 20"
        )

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        for row in rows:
            if row.get("min_price") is not None:
                row["min_price"] = float(row["min_price"])
            if row.get("max_price") is not None:
                row["max_price"] = float(row["max_price"])

        return rows
    except Exception:
        return []
    finally:
        cursor.close()
        conn.close()


def _mock_mysql_query(profile: dict) -> list[dict]:
    """Mock MySQL query for development/demo when DB is unavailable."""
    insurance_type = profile.get("insurance_type", "重疾险")
    age = profile.get("age", 30)
    budget = profile.get("budget", 5000)
    occupation = profile.get("occupation", "")

    mock_products = [
        {
            "product_id": "CI001",
            "product_name": "安心保·重疾险（标准版）",
            "insurance_type": "重疾险",
            "min_age": 18,
            "max_age": 55,
            "min_price": 3000.0,
            "max_price": 8000.0,
            "target_occupations": "程序员,IT从业者,工程师,白领",
            "description": "覆盖120种重疾，含轻症豁免，适合IT从业者的高性价比重疾保障。",
        },
        {
            "product_id": "CI002",
            "product_name": "健康守护·终身重疾险",
            "insurance_type": "重疾险",
            "min_age": 0,
            "max_age": 50,
            "min_price": 5000.0,
            "max_price": 15000.0,
            "target_occupations": "程序员,教师,医生,公务员,白领",
            "description": "终身保障，150种重疾+50种轻症，含身故返保费。",
        },
        {
            "product_id": "CI003",
            "product_name": "年轻保·重疾险（基础版）",
            "insurance_type": "重疾险",
            "min_age": 18,
            "max_age": 35,
            "min_price": 1500.0,
            "max_price": 4000.0,
            "target_occupations": "程序员,设计师,运营,应届生",
            "description": "专为年轻人定制的入门级重疾险，低保费高杠杆。",
        },
        {
            "product_id": "MI001",
            "product_name": "全民e保·百万医疗险",
            "insurance_type": "医疗险",
            "min_age": 0,
            "max_age": 65,
            "min_price": 200.0,
            "max_price": 2000.0,
            "target_occupations": "全部职业",
            "description": "400万医疗保障，不限社保用药，含质子重离子治疗。",
        },
        {
            "product_id": "AC001",
            "product_name": "平安行·综合意外险",
            "insurance_type": "意外险",
            "min_age": 18,
            "max_age": 60,
            "min_price": 100.0,
            "max_price": 1000.0,
            "target_occupations": "全部职业",
            "description": "高额意外保障，含猝死责任，适合经常出差的职场人士。",
        },
    ]

    matched = []
    for p in mock_products:
        if p["insurance_type"] != insurance_type:
            continue
        if not (p["min_age"] <= age <= p["max_age"]):
            continue
        if budget < p["min_price"]:
            continue
        if occupation and occupation not in p["target_occupations"]:
            continue
        matched.append(p)

    return matched


# ---------------------------------------------------------------------------
# Tool 3: RAG enrichment search（Milvus 向量检索，复用 shared/milvus_utils）
# ---------------------------------------------------------------------------

def _build_rag_queries(
    product: dict,
    profile: dict | None = None,
) -> list[str]:
    """为单个产品构建多路检索查询。

    3 条查询覆盖不同维度：
    1. 产品专项：产品名称 + 险种 + 保障/理赔/适用人群
    2. 通用知识：险种 + 条款/既往症/费率/免责/常见问题
    3. 用户画像（如有）：年龄 + 职业 + 预算 + 险种 + 推荐/注意事项
    """
    product_name = product.get("product_name", "")
    insurance_type = product.get("insurance_type", "")

    queries = []

    queries.append(
        f"{product_name} {insurance_type} 保障范围 适用人群 理赔案例 产品特点 保费"
    )

    queries.append(
        f"{insurance_type} 条款说明 既往症 费率表 投保规则 免责条款 常见问题 药品范围"
    )

    if profile and profile.get("age") and profile.get("insurance_type"):
        age = profile.get("age", "")
        occupation = profile.get("occupation", "")
        budget = profile.get("budget", "")
        ins_type = profile.get("insurance_type", insurance_type)
        queries.append(
            f"{age}岁 {occupation} 预算{budget}元 {ins_type} 保险推荐 投保建议 注意事项"
        )

    return queries


@tool
def rag_enrich_products(
    product_ids_json: str,
    products_json: str = "",
    profile_json: str = "",
) -> list[dict]:
    """使用 Milvus 向量检索为匹配产品补充上下文信息。

    检索策略（每个产品 3 路查询）：
    1. 产品专项：产品名 + 险种 + 保障/理赔/适用人群
    2. 通用知识：险种 + 条款/既往症/费率/免责/常见问题
    3. 用户画像匹配：年龄 + 职业 + 预算 + 险种 + 推荐建议
    """
    product_ids = (
        json.loads(product_ids_json)
        if isinstance(product_ids_json, str)
        else product_ids_json
    )

    products_list: list[dict] = []
    if products_json:
        try:
            products_list = (
                json.loads(products_json)
                if isinstance(products_json, str)
                else products_json
            )
        except (json.JSONDecodeError, TypeError):
            pass

    profile: dict | None = None
    if profile_json:
        try:
            profile = (
                json.loads(profile_json)
                if isinstance(profile_json, str)
                else profile_json
            )
        except (json.JSONDecodeError, TypeError):
            pass

    product_map: dict[str, dict] = {p.get("product_id", ""): p for p in products_list}

    if not is_milvus_available():
        return _mock_rag_enrich(product_ids, products_list, profile)

    embed_func = get_embedding_function()
    if embed_func is None:
        return _mock_rag_enrich(product_ids, products_list, profile)

    enriched = []
    seen_texts: set[str] = set()

    for pid in product_ids:
        product = product_map.get(pid, {"product_id": pid, "product_name": pid, "insurance_type": ""})
        queries = _build_rag_queries(product, profile)

        all_hits: list[dict] = []
        for query in queries:
            try:
                hits = milvus_search(query, top_k=RAG_TOP_K)
                all_hits.extend(hits)
            except Exception:
                continue

        unique_texts: list[str] = []
        for hit in sorted(all_hits, key=lambda h: h["score"], reverse=True):
            key = hit["text"][:100].strip()
            if key not in seen_texts:
                seen_texts.add(key)
                source = hit.get("file_path", "").replace("\\", "/").split("/")[-1]
                unique_texts.append(
                    f"【来源: {source}】(相关度: {hit['score']:.2f})\n{hit['text']}"
                )

        if unique_texts:
            rag_content = "\n\n---\n\n".join(unique_texts)
        else:
            rag_content = f"产品{pid}的补充资料暂无，建议基于产品基本信息进行推荐。"

        enriched.append({"product_id": pid, "rag_content": rag_content})

    return enriched


def _mock_rag_enrich(
    product_ids: list[str],
    products_list: list[dict] | None = None,
    profile: dict | None = None,
) -> list[dict]:
    """Mock RAG enrichment — 当 Milvus 不可用时的兜底方案。"""
    mock_cases: dict[str, str] = {
        "CI001": (
            "【产品案例】张先生，30岁，程序员，投保'安心保·重疾险（标准版）'，年缴保费4500元。"
            "2024年确诊甲状腺癌，获得赔付50万元，并豁免后续保费。\n"
            "【适用人群】18-55岁IT从业者、白领，预算3000-8000元/年。\n"
            "【保障亮点】覆盖120种重疾，含轻症三次赔付，确诊即赔。"
        ),
        "CI002": (
            "【产品案例】李女士，35岁，教师，投保'健康守护·终身重疾险'，年缴保费8000元。"
            "因乳腺癌获得全额赔付100万元，含术后康复津贴。\n"
            "【适用人群】0-50岁全职业人群，预算5000元/年以上。\n"
            "【保障亮点】150种重疾+50种轻症，终身保障，含身故责任。"
        ),
        "CI003": (
            "【产品案例】王先生，25岁，应届生，投保'年轻保·重疾险（基础版）'，年缴保费2000元。"
            "获得30万基础保额，随年龄增长保额自动提升。\n"
            "【适用人群】18-35岁年轻人，预算有限但需要基础保障。\n"
            "【保障亮点】低保费入门，保额逐年递增，可升级至高端版本。"
        ),
        "MI001": (
            "【产品案例】赵女士，45岁，自由职业，投保'全民e保·百万医疗险'，年缴保费680元。"
            "因住院手术获赔15万元，自费药全额报销。\n"
            "【适用人群】0-65岁所有职业，预算200-2000元/年。\n"
            "【保障亮点】400万保额，不限社保，含质子重离子。"
        ),
        "AC001": (
            "【产品案例】陈先生，28岁，销售经理，投保'平安行·综合意外险'，年缴保费360元。"
            "出差途中交通事故获赔80万元。\n"
            "【适用人群】18-60岁所有职业，预算100-1000元/年。\n"
            "【保障亮点】高额意外+猝死保障，24小时全球保障。"
        ),
    }

    general_knowledge: dict[str, str] = {
        "重疾险": (
            "【重疾险通用知识】\n"
            "1. 保障范围：覆盖恶性肿瘤、急性心肌梗死、脑中风后遗症、重大器官移植等核心重疾。\n"
            "2. 投保规则：通常要求被保险人年龄0-55岁，需健康告知，既往症可能除外或加费。\n"
            "3. 等待期：一般90-180天，等待期内出险不赔付。\n"
            "4. 保费说明：年龄越大保费越高，30岁左右年缴3000-8000元可获30-50万保额。\n"
            "5. 注意事项：关注轻症赔付比例、多次赔付间隔期、是否含身故责任、豁免条款。"
        ),
        "医疗险": (
            "【医疗险通用知识】\n"
            "1. 保障范围：住院医疗、特殊门诊、门诊手术、住院前后门急诊，不限社保用药。\n"
            "2. 投保规则：0-65岁可投，部分产品支持带病投保（除外既往症），需注意续保条件。\n"
            "3. 免赔额：通常1万元/年，百万医疗险保费200-2000元/年。\n"
            "4. 等待期：一般30天，意外伤害无等待期。\n"
            "5. 注意事项：关注续保条款、质子重离子覆盖、外购药报销、就医绿通。"
        ),
        "意外险": (
            "【意外险通用知识】\n"
            "1. 保障范围：意外身故/伤残、意外医疗、猝死（部分产品）、意外住院津贴。\n"
            "2. 投保规则：18-60岁，无需健康告知，职业类别影响保费和承保。\n"
            "3. 保费说明：100-1000元/年可获50-100万保额，性价比极高。\n"
            "4. 注意事项：关注职业类别限制、免赔额、报销比例、是否全球保障。"
        ),
        "寿险": (
            "【寿险通用知识】\n"
            "1. 保障范围：身故/全残，定期寿险保固定年限，终身寿险保终身。\n"
            "2. 投保规则：18-60岁，需健康告知，保额通常为年收入5-10倍。\n"
            "3. 保费说明：定期寿险30岁左右年缴1000-3000元可获100万保额。\n"
            "4. 注意事项：关注免责条款、等待期、转换权（定期转终身）。"
        ),
        "年金险": (
            "【年金险通用知识】\n"
            "1. 保障范围：约定年龄起按月/年领取年金，保障退休收入。\n"
            "2. 投保规则：通常0-60岁可投，缴费期5-20年，领取年龄55-65岁。\n"
            "3. 收益说明：保证领取年限（通常20年），IRR约2.5%-3.5%。\n"
            "4. 注意事项：关注保证领取期、现金价值、万能账户结算利率。"
        ),
    }

    enriched = []
    for pid in product_ids:
        parts: list[str] = []

        case = mock_cases.get(pid, f"产品{pid}的案例资料暂无。")
        if case:
            parts.append(f"【产品资料】\n{case}")

        product_map = {}
        if products_list:
            product_map = {p.get("product_id", ""): p for p in products_list}
        product = product_map.get(pid, {})
        insurance_type = product.get("insurance_type", "")
        if insurance_type and insurance_type in general_knowledge:
            parts.append(general_knowledge[insurance_type])

        if profile and profile.get("age") and profile.get("insurance_type"):
            parts.append(
                f"【用户画像参考】用户{profile.get('age')}岁，{profile.get('occupation')}，"
                f"预算{profile.get('budget')}元/年，意向{profile.get('insurance_type')}。"
                f"请结合用户实际情况给出个性化推荐理由。"
            )

        rag_content = "\n\n".join(parts) if parts else f"产品{pid}的相关资料暂无。"
        enriched.append({"product_id": pid, "rag_content": rag_content})

    return enriched


# ---------------------------------------------------------------------------
# Helper: validate profile and identify missing fields
# ---------------------------------------------------------------------------

def validate_user_profile(profile: dict) -> list[str]:
    """Check which required fields are missing or invalid.

    Returns:
        List of Chinese field names that are missing.
    """
    missing = []
    for field, label in REQUIRED_FIELDS.items():
        value = profile.get(field)
        if value is None or value == "" or value == 0:
            missing.append(label)
    return missing
