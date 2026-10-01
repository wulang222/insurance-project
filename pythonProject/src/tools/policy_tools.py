"""Eligibility, evidence and coverage analysis tools."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from harness.errors import DependencyUnavailableError
from tools.product_tools import Product


class EligibilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: Product
    age: int = Field(ge=0, le=120)
    occupation: str
    budget: float = Field(ge=0)


class EligibilityResult(BaseModel):
    eligible: bool
    reasons: list[str] = Field(default_factory=list)


def get_product_eligibility(
    product: Product,
    age: int,
    occupation: str,
    budget: float,
) -> EligibilityResult:
    reasons: list[str] = []
    if product.min_age is not None and age < product.min_age:
        reasons.append("年龄低于承保范围")
    if product.max_age is not None and age > product.max_age:
        reasons.append("年龄高于承保范围")
    if product.min_price is not None and budget < product.min_price:
        reasons.append("预算低于最低保费")
    if (
        occupation
        and occupation not in product.target_occupations
        and "全部职业" not in product.target_occupations
    ):
        reasons.append("职业不在承保范围")
    return EligibilityResult(eligible=not reasons, reasons=reasons)


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    product_ids: list[str] = Field(default_factory=list)
    top_k: int = Field(default=6, ge=1, le=20)


class Evidence(BaseModel):
    content: str
    source: str = ""
    score: float = 0
    product_id: str | None = None


class PolicyEvidenceRepository(Protocol):
    def search(self, query: str, *, product_ids: list[str], top_k: int) -> list[dict[str, Any]]: ...


class MilvusPolicyEvidenceRepository:
    def __init__(self, client: Any | None = None) -> None:
        self.client = client

    def search(self, query: str, *, product_ids: list[str], top_k: int) -> list[dict[str, Any]]:
        if self.client is not None:
            return self._search_owned_client(query, product_ids=product_ids, top_k=top_k)

        from shared.milvus_utils import is_milvus_available, milvus_search

        if not is_milvus_available():
            raise DependencyUnavailableError(
                "Milvus or embedding provider is unavailable",
                details={"dependency": "milvus"},
                retryable=True,
            )
        try:
            hits = milvus_search(query, top_k=top_k)
        except Exception as exc:
            raise DependencyUnavailableError(
                "Milvus evidence search failed",
                details={"dependency": "milvus"},
                retryable=True,
            ) from exc
        evidence: list[dict[str, Any]] = []
        for hit in hits:
            metadata = hit.get("metadata") or {}
            product_id = metadata.get("product_id")
            if product_ids and product_id and product_id not in product_ids:
                continue
            evidence.append(
                {
                    "content": str(hit.get("text", "")),
                    "source": str(hit.get("file_path", "")),
                    "score": float(hit.get("score", 0)),
                    "product_id": product_id,
                }
            )
        return evidence

    def _search_owned_client(
        self,
        query: str,
        *,
        product_ids: list[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        import os

        from pymilvus import Collection, utility
        from shared.milvus_utils import get_embedding_function

        try:
            self.client.connect()
            collection_name = os.getenv("MILVUS_COLLECTION", "file_documents")
            if not utility.has_collection(collection_name, using=self.client.alias):
                return []
            embed = get_embedding_function()
            if embed is None:
                raise DependencyUnavailableError(
                    "Embedding provider is unavailable",
                    details={"dependency": "embedding"},
                    retryable=True,
                )
            collection = Collection(collection_name, using=self.client.alias)
            collection.load()
            results = collection.search(
                data=[embed([query])[0]],
                anns_field="embedding",
                param={"metric_type": "IP", "params": {"nprobe": 10}},
                limit=top_k,
                output_fields=["text", "file_path", "metadata"],
            )
            evidence: list[dict[str, Any]] = []
            for hit in results[0]:
                metadata = hit.entity.get("metadata", {}) or {}
                product_id = metadata.get("product_id")
                if product_ids and product_id and product_id not in product_ids:
                    continue
                evidence.append(
                    {
                        "content": str(hit.entity.get("text", "")),
                        "source": str(hit.entity.get("file_path", "")),
                        "score": float(hit.score),
                        "product_id": product_id,
                    }
                )
            return evidence
        except DependencyUnavailableError:
            raise
        except Exception as exc:
            raise DependencyUnavailableError(
                "Milvus evidence repository is unavailable",
                details={"dependency": "milvus"},
                retryable=True,
            ) from exc


class FakePolicyEvidenceRepository:
    def __init__(self, evidence: list[dict[str, Any]]) -> None:
        self.evidence = evidence

    def search(self, query: str, *, product_ids: list[str], top_k: int) -> list[dict[str, Any]]:
        del query
        values = [
            item
            for item in self.evidence
            if not product_ids or item.get("product_id") in product_ids
        ]
        return values[:top_k]


class CoverageGapInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    portfolio: list[dict[str, Any]] = Field(default_factory=list)
    desired_types: list[str] = Field(default_factory=lambda: ["重疾险", "医疗险", "意外险", "寿险"])


class CoverageGapResult(BaseModel):
    covered_types: list[str]
    missing_types: list[str]


def calculate_coverage_gap(
    portfolio: list[dict[str, Any]],
    desired_types: list[str],
) -> CoverageGapResult:
    covered = sorted(
        {
            str(policy.get("insurance_type"))
            for policy in portfolio
            if policy.get("status") in ("active", "expiring_soon")
            and policy.get("insurance_type")
        }
    )
    return CoverageGapResult(
        covered_types=covered,
        missing_types=[item for item in desired_types if item not in covered],
    )
