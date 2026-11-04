"""Vector stores for one-document ingest. Neither implementation rebuilds a collection."""

from __future__ import annotations

from typing import Any, Protocol


class DocumentVectorStore(Protocol):
    def insert(self, rows: list[dict[str, Any]]) -> None: ...

    def delete_generation(self, document_id: str, generation: str) -> None: ...

    def delete_other_generations(self, document_id: str, keep_generation: str) -> None: ...

    def list_chunks(self, document_id: str) -> list[dict[str, Any]]: ...

    def search_text(self, query: str) -> list[dict[str, Any]]: ...


class MemoryVectorStore:
    """Test double that can fail after a partial insert."""

    def __init__(self, *, fail_after: int | None = None) -> None:
        self.rows: list[dict[str, Any]] = []
        self.fail_after = fail_after
        self._inserted = 0
        self.recreate_collection_calls = 0

    def insert(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self.rows.append(row)
            self._inserted += 1
            if self.fail_after is not None and self._inserted >= self.fail_after:
                raise RuntimeError("vector insert failed")

    def delete_generation(self, document_id: str, generation: str) -> None:
        self.rows = [
            row
            for row in self.rows
            if not (row["document_id"] == document_id and row["generation"] == generation)
        ]

    def delete_other_generations(self, document_id: str, keep_generation: str) -> None:
        self.rows = [
            row
            for row in self.rows
            if not (
                row["document_id"] == document_id and row["generation"] != keep_generation
            )
        ]

    def list_chunks(self, document_id: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows if row["document_id"] == document_id]

    def search_text(self, query: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows if query in str(row["text"])]


class MilvusDocumentStore:
    """Writes one generation into an existing collection and never recreates it."""

    def __init__(self, collection: Any) -> None:
        self.collection = collection
        self.recreate_collection_calls = 0

    def insert(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self.collection.insert(
            [
                [row["text"] for row in rows],
                [row["embedding"] for row in rows],
                [row["file_path"] for row in rows],
                [row["file_type"] for row in rows],
                [row["chunk_index"] for row in rows],
                [row["metadata"] for row in rows],
            ]
        )

    def delete_generation(self, document_id: str, generation: str) -> None:
        self.collection.delete(
            f'metadata["document_id"] == "{document_id}" and metadata["generation"] == "{generation}"'
        )

    def delete_other_generations(self, document_id: str, keep_generation: str) -> None:
        self.collection.delete(
            f'metadata["document_id"] == "{document_id}" and metadata["generation"] != "{keep_generation}"'
        )

    def list_chunks(self, document_id: str) -> list[dict[str, Any]]:
        rows = self.collection.query(
            expr=f'metadata["document_id"] == "{document_id}"',
            output_fields=["text", "file_path", "metadata"],
        )
        return [
            {"text": row.get("text", ""), "metadata": row.get("metadata") or {}, "file_path": row.get("file_path", "")}
            for row in rows
        ]

    def search_text(self, query: str) -> list[dict[str, Any]]:
        del query
        return []


class ExistingMilvusDocumentStore:
    """Uses the collection that already exists. It never creates or drops one."""

    def __init__(self) -> None:
        self.recreate_collection_calls = 0
        self._delegate: MilvusDocumentStore | None = None

    def _store(self) -> MilvusDocumentStore:
        if self._delegate is None:
            from shared.milvus_utils import get_milvus_collection

            collection = get_milvus_collection()
            if collection is None:
                raise RuntimeError("milvus collection is unavailable")
            self._delegate = MilvusDocumentStore(collection)
        return self._delegate

    def insert(self, rows: list[dict[str, Any]]) -> None:
        self._store().insert(rows)

    def delete_generation(self, document_id: str, generation: str) -> None:
        self._store().delete_generation(document_id, generation)

    def delete_other_generations(self, document_id: str, keep_generation: str) -> None:
        self._store().delete_other_generations(document_id, keep_generation)

    def list_chunks(self, document_id: str) -> list[dict[str, Any]]:
        return self._store().list_chunks(document_id)

    def search_text(self, query: str) -> list[dict[str, Any]]:
        return self._store().search_text(query)
