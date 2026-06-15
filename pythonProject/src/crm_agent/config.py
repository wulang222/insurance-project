"""CRM Agent 配置"""

from __future__ import annotations

import os
from typing import Any

# LLM 配置（复用通义千问）
DEFAULT_MODEL = os.getenv("CRM_AGENT_MODEL", "qwen3.7-plus")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

LLM_TEMPERATURE = 0.3  # CRM分析需要更稳定
LLM_EXTRA_BODY: dict[str, Any] = {"thinking": {"type": "disabled"}}


def create_llm(temperature: float | None = None) -> Any:
    """创建 ChatOpenAI 实例（通义千问 / DashScope）"""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=DEFAULT_MODEL,
        api_key=DASHSCOPE_API_KEY,
        base_url=DASHSCOPE_BASE_URL,
        temperature=temperature if temperature is not None else LLM_TEMPERATURE,
        extra_body=LLM_EXTRA_BODY,
    )
