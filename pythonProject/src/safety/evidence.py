"""Retrieval post-processing: rerank, deduplicate and build an evidence pack."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from harness.result import Citation
from tools.policy_tools import Evidence


_PROMPT_INJECTION_PATTERNS = (
    r"忽略(?:之前|以上|系统|所有).{0,12}(?:提示|指令|规则)",
    r"(?:系统|开发者)提示词",
    r"你现在是",
    r"ignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions?",
    r"system\s+prompt",
)


class EvidencePack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def build_evidence_pack(
    query: str,
    raw_evidence: list[Evidence | dict[str, Any]],
    *,
    product_ids: list[str] | None = None,
    top_k: int = 6,
) -> EvidencePack:
    """Treat retrieved text as untrusted data and return evidence only."""

    allowed_products = set(product_ids or [])
    warnings: list[str] = []
    deduplicated: dict[tuple[str, str, int | None, str], Evidence] = {}
    for raw in raw_evidence:
        evidence = raw if isinstance(raw, Evidence) else Evidence.model_validate(raw)
        if allowed_products and evidence.product_id and evidence.product_id not in allowed_products:
            continue
        if _contains_prompt_injection(evidence.content):
            warnings.append(
                f"已隔离疑似提示词注入证据：{evidence.document_id}，该内容不会进入回答上下文。"
            )
            continue
        key = (evidence.document_id, evidence.section or "", evidence.page, evidence.checksum)
        current = deduplicated.get(key)
        if current is None or evidence.score > current.score:
            deduplicated[key] = evidence

    query_terms = {term.lower() for term in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", query)}

    def rerank_score(item: Evidence) -> tuple[float, float]:
        text = f"{item.title} {item.section or ''} {item.content}".lower()
        overlap = sum(1 for term in query_terms if term in text)
        return (item.score + overlap * 0.01, item.score)

    ranked = sorted(deduplicated.values(), key=rerank_score, reverse=True)[:top_k]
    if not ranked:
        warnings.append("未检索到可验证证据；相关条款结论不确定，需人工确认。")
    return EvidencePack(query=query, evidence=ranked, warnings=warnings)


def citation_from_evidence(evidence: Evidence, claim: str | None = None) -> Citation:
    seed = f"{evidence.document_id}|{evidence.section}|{evidence.page}|{evidence.checksum}"
    citation_id = f"CIT-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"
    excerpt = evidence.content.strip()[:400]
    return Citation(
        citation_id=citation_id,
        claim=(claim or excerpt)[:240],
        document_id=evidence.document_id,
        title=evidence.title,
        section=evidence.section,
        page=evidence.page,
        excerpt=excerpt,
        score=evidence.score,
        source_version=evidence.version,
    )


def _contains_prompt_injection(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _PROMPT_INJECTION_PATTERNS)
