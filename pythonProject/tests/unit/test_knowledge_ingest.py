"""Single-document ingest keeps old vectors until the new write succeeds."""

from __future__ import annotations

import base64
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from knowledge.api import build_knowledge_router
from knowledge.ingest import ingest_document
from knowledge.store import MemoryVectorStore, MilvusDocumentStore


def _embed(texts: list[str]) -> list[list[float]]:
    return [[float(len(text)), 0.5] for text in texts]


def _ingest(store: MemoryVectorStore, document_id: str, filename: str, text: str) -> str:
    return ingest_document(
        document_id=document_id,
        filename=filename,
        content=text.encode(),
        title="重疾条款",
        product_id="CI001",
        checksum="abc123",
        source_path=f"oss/{filename}",
        store=store,
        embed=_embed,
        chunk_size=8,
        chunk_overlap=0,
    )


def test_successful_ingest_keeps_other_documents_and_citation_metadata() -> None:
    store = MemoryVectorStore()
    store.rows.append(
        {
            "document_id": "other",
            "generation": "old",
            "text": "其他文档不受影响",
            "metadata_dict": {"document_id": "other"},
        }
    )

    _ingest(store, "15", "clause.md", "等待期三十天。这是新条款。")

    own = store.list_chunks("15")
    assert own
    assert store.search_text("其他文档不受影响")
    metadata = own[0]["metadata_dict"]
    assert metadata["title"] == "重疾条款"
    assert metadata["checksum"] == "abc123"
    assert metadata["product_id"] == "CI001"
    assert metadata["source_path"] == "oss/clause.md"
    assert store.recreate_collection_calls == 0


def test_failed_insert_removes_only_the_new_generation() -> None:
    store = MemoryVectorStore(fail_after=1)
    store.rows.append(
        {
            "document_id": "15",
            "generation": "published",
            "text": "已经发布的旧条款",
            "metadata_dict": {"document_id": "15"},
        }
    )
    store.rows.append(
        {
            "document_id": "other",
            "generation": "kept",
            "text": "旁边的文档",
            "metadata_dict": {"document_id": "other"},
        }
    )

    try:
        _ingest(store, "15", "clause.txt", "新版本第一段。\n\n新版本第二段。")
    except Exception as exc:
        assert "vector insert failed" in str(exc)
    else:
        raise AssertionError("partial insert must fail the ingest")

    texts = [row["text"] for row in store.rows]
    assert "已经发布的旧条款" in texts
    assert "旁边的文档" in texts
    assert all(row["generation"] != store.rows[-1]["generation"] or row["document_id"] != "15" for row in store.rows)
    assert not any(row["document_id"] == "15" and row["generation"] != "published" for row in store.rows)


def test_replacement_drops_previous_chunks_after_success() -> None:
    store = MemoryVectorStore()
    _ingest(store, "15", "clause.md", "旧条款阿尔法")
    _ingest(store, "15", "clause.md", "新条款贝塔")

    assert store.search_text("新条款贝塔")
    assert not store.search_text("旧条款阿尔法")


def test_milvus_adapter_deletes_old_generation_without_recreating_collection() -> None:
    class Collection:
        def __init__(self) -> None:
            self.deleted: list[str] = []

        def insert(self, columns: list) -> None:
            assert len(columns) == 6

        def delete(self, expr: str) -> None:
            self.deleted.append(expr)

        def query(self, expr: str, output_fields: list[str]) -> list:
            del expr, output_fields
            return []

    collection = Collection()
    store = MilvusDocumentStore(collection)
    _ingest(store, "15", "clause.md", "条款正文")
    assert store.recreate_collection_calls == 0
    assert any('metadata["document_id"] == "15"' in expr and "!=" in expr for expr in collection.deleted)


def test_internal_api_rejects_bad_token_and_lists_chunks() -> None:
    store = MemoryVectorStore()
    app = FastAPI()
    app.include_router(build_knowledge_router(store=store, embed=_embed, token="secret"))
    client = TestClient(app)

    denied = client.post(
        "/internal/knowledge/ingest",
        headers={"X-Internal-Token": "wrong"},
        json={
            "document_id": 15,
            "filename": "clause.md",
            "content_base64": base64.b64encode("条款".encode()).decode(),
            "title": "重疾条款",
            "checksum": "abc123",
            "product_id": "CI001",
        },
    )
    assert denied.status_code == 401
    assert store.recreate_collection_calls == 0

    accepted = client.post(
        "/internal/knowledge/ingest",
        headers={"X-Internal-Token": "secret"},
        json={
            "document_id": 15,
            "filename": "clause.md",
            "content_base64": base64.b64encode("等待期三十天".encode()).decode(),
            "title": "重疾条款",
            "checksum": "abc123",
            "product_id": "CI001",
            "source_path": "oss/clause.md",
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["chunk_count"] >= 1

    listed = client.get(
        "/internal/knowledge/documents/15/chunks",
        headers={"X-Internal-Token": "secret"},
    )
    body = listed.json()["chunks"][0]
    metadata = body["metadata"]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    assert "等待期" in body["text"]
    assert metadata["title"] == "重疾条款"
    assert metadata["checksum"] == "abc123"
    assert metadata["product_id"] == "CI001"
