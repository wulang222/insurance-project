"""
知识回答Agent — 状态定义（TypedDict，LangGraph 原生支持）
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class KnowledgeAgentState(TypedDict, total=False):
    """知识回答Agent的状态容器

    各字段说明：
    - messages:             完整对话历史（Annotated + add_messages 累加）
    - user_id:              用户标识（用于跨会话 Store 读写）
    - raw_question:         用户当前输入的原始问题
    - rewritten_question:   LLM结合历史重写后的完整问题
    - user_context:         从Store加载的用户上下文(画像/偏好/历史)
    - intent:               意图分类: "db" 走数据库 / "rag" 走知识库
    - db_results:           数据库查询返回的结构化数据列表
    - rag_docs:             RAG检索返回的知识文档片段列表
    - final_answer:         最终生成的知识解答文本
    """
    messages: Annotated[list, add_messages]
    user_id: str
    raw_question: str
    rewritten_question: str
    user_context: dict
    intent: str
    db_results: list[dict]
    rag_docs: list[dict]
    final_answer: str
    warnings: list[str]
