"""Internal knowledge API. It is not registered on the public gateway."""

from __future__ import annotations

import base64
from collections.abc import Callable

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from knowledge.ingest import ingest_document
from knowledge.store import DocumentVectorStore


class IngestBody(BaseModel):
    document_id: str | int
    filename: str
    content_base64: str
    title: str
    checksum: str
    product_id: str | None = None
    source_path: str | None = None


class ChunkBody(BaseModel):
    text: str
    metadata: dict = Field(default_factory=dict)


def build_knowledge_router(
    *,
    store: DocumentVectorStore,
    embed: Callable[[list[str]], list[list[float]]],
    token: str,
) -> APIRouter:
    router = APIRouter()

    def authorize(presented: str | None) -> None:
        if not token or presented != token:
            raise HTTPException(status_code=401, detail="unauthorized")

    @router.post("/internal/knowledge/ingest")
    def ingest(
        body: IngestBody,
        x_internal_token: str | None = Header(default=None),
    ) -> dict:
        authorize(x_internal_token)
        try:
            content = base64.b64decode(body.content_base64)
            generation = ingest_document(
                document_id=str(body.document_id),
                filename=body.filename,
                content=content,
                title=body.title,
                product_id=body.product_id,
                checksum=body.checksum,
                source_path=body.source_path or body.filename,
                store=store,
                embed=embed,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        stored = store.list_chunks(str(body.document_id))
        return {"chunk_count": len(stored), "generation": generation}

    @router.get("/internal/knowledge/documents/{document_id}/chunks")
    def chunks(
        document_id: str,
        x_internal_token: str | None = Header(default=None),
    ) -> dict:
        authorize(x_internal_token)
        rows = []
        for row in store.list_chunks(document_id):
            metadata = row.get("metadata_dict") or row.get("metadata") or {}
            if isinstance(metadata, str):
                import json

                metadata = json.loads(metadata)
            rows.append(ChunkBody(text=str(row.get("text", "")), metadata=metadata).model_dump())
        return {"chunks": rows}

    return router
