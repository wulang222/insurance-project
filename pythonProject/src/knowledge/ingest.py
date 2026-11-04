"""Ingest one clause file. New vectors are kept only after every batch succeeds."""

from __future__ import annotations

import json
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from knowledge.store import DocumentVectorStore


class IngestError(RuntimeError):
    """The document was not published. Previous generations stay in place."""


def ingest_document(
    *,
    document_id: str,
    filename: str,
    content: bytes,
    title: str,
    product_id: str | None,
    checksum: str,
    source_path: str,
    store: DocumentVectorStore,
    embed: Callable[[list[str]], list[list[float]]],
    chunk_size: int = 1024,
    chunk_overlap: int = 200,
) -> str:
    """Return the published generation id."""

    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".md", ".txt"}:
        raise IngestError("unsupported file type")
    generation = uuid.uuid4().hex
    try:
        chunks = _chunks(
            filename=filename,
            content=content,
            title=title,
            product_id=product_id,
            checksum=checksum,
            source_path=source_path,
            document_id=document_id,
            generation=generation,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        vectors = embed([chunk.text for chunk in chunks])
        if len(vectors) != len(chunks):
            raise IngestError("embedding count does not match chunks")
        rows = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            rows.append(
                {
                    "document_id": document_id,
                    "generation": generation,
                    "text": chunk.text,
                    "embedding": vector,
                    "file_path": source_path,
                    "file_type": chunk.file_type,
                    "chunk_index": chunk.chunk_index,
                    "metadata": json.dumps(chunk.metadata, ensure_ascii=False),
                    "metadata_dict": chunk.metadata,
                }
            )
        store.insert(rows)
        store.delete_other_generations(document_id, generation)
    except Exception as exc:
        try:
            store.delete_generation(document_id, generation)
        except Exception:
            pass
        if isinstance(exc, IngestError):
            raise
        raise IngestError(str(exc)) from exc
    return generation


def _chunks(
    *,
    filename: str,
    content: bytes,
    title: str,
    product_id: str | None,
    checksum: str,
    source_path: str,
    document_id: str,
    generation: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Any]:
    from vectorizer.chunker import chunk_document
    from vectorizer.config import VectorizerConfig
    from vectorizer.loader import load_file

    suffix = Path(filename).suffix.lower()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / f"document{suffix}"
        path.write_bytes(content)
        loaded = load_file(path)
    if loaded is None or not str(loaded.get("content", "")).strip():
        raise IngestError("document has no text")
    loaded["metadata"].update(
        {
            "document_id": document_id,
            "generation": generation,
            "title": title,
            "product_id": product_id,
            "checksum": checksum,
            "source_path": source_path,
            "document_type": suffix.lstrip(".") or "unknown",
            "version": generation,
        }
    )
    config = VectorizerConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = chunk_document(loaded, config)
    if not chunks:
        raise IngestError("document has no chunks")
    return chunks
