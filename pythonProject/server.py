"""FastAPI entrypoint for legacy Chat and durable Run APIs."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from api.models import (  # noqa: E402
    ChatRequest,
    ChatResponse,
    CreateRunRequest,
    ResumeRunRequest,
    RunResponse,
)
from harness.lifecycle import production_lifespan  # noqa: E402
from harness.runtime import (  # noqa: E402
    InvalidRunStateError,
    RunManager,
    RunNotFoundError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(
    *,
    lifespan: Callable[[FastAPI], AbstractAsyncContextManager[None]] = production_lifespan,
) -> FastAPI:
    app = FastAPI(
        title="Insurance AI Server",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health(request: Request) -> dict:
        ready = getattr(request.app.state, "runtime", None) is not None
        return {
            "status": "ok" if ready else "starting",
            "agent": "supervisor_agent",
            "runtime": "ready" if ready else "unavailable",
        }

    @app.get("/v1/metrics")
    async def metrics(request: Request) -> dict:
        observability = getattr(request.app.state, "observability", None)
        if observability is None:
            runtime = _runtime(request)
            observability = runtime.observability
        return observability.metrics.snapshot()

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest, request: Request) -> ChatResponse:
        """Legacy Java-compatible endpoint backed by the same durable runtime."""

        runtime = _runtime(request)
        snapshot = await runtime.start(
            req.message,
            user_id=req.user_id,
            thread_id=req.session_id or None,
        )
        response = RunResponse.from_snapshot(snapshot)
        if response.status == "failed":
            raise HTTPException(status_code=500, detail=response.error)
        return ChatResponse(
            session_id=response.thread_id,
            message_id=response.run_id,
            content=response.answer,
            handled_by=response.handled_by[0] if response.handled_by else "",
            route=str(response.structured_data.get("route", "")),
            route_reason=str(response.structured_data.get("route_reason", "")),
        )

    @app.post("/chat/stream")
    async def chat_stream(req: ChatRequest, request: Request) -> StreamingResponse:
        """Legacy SSE endpoint with the same run identity and persistence semantics."""

        runtime = _runtime(request)

        async def event_generator() -> AsyncIterator[str]:
            snapshot = await runtime.start(
                req.message,
                user_id=req.user_id,
                thread_id=req.session_id or None,
            )
            response = RunResponse.from_snapshot(snapshot)
            yield _sse(
                {
                    "session_id": response.thread_id,
                    "message_id": response.run_id,
                    "delta": response.answer,
                    "status": response.status,
                    "handled_by": (
                        response.handled_by[0] if response.handled_by else ""
                    ),
                    "route": response.structured_data.get("route", ""),
                    "route_reason": response.structured_data.get("route_reason", ""),
                    "required_input": response.required_input,
                }
            )
            yield _sse(
                {
                    "session_id": response.thread_id,
                    "message_id": response.run_id,
                    "delta": "",
                    "done": True,
                    "status": response.status,
                }
            )

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/v1/runs", response_model=RunResponse)
    async def create_run(req: CreateRunRequest, request: Request) -> RunResponse:
        snapshot = await _runtime(request).start(
            req.message,
            user_id=req.user_id,
            thread_id=req.thread_id,
            request_id=req.request_id,
        )
        return RunResponse.from_snapshot(snapshot)

    @app.get("/v1/runs/{run_id}", response_model=RunResponse)
    async def get_run(run_id: str, request: Request) -> RunResponse:
        try:
            snapshot = await _runtime(request).get(run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=exc.to_dict()) from exc
        return RunResponse.from_snapshot(snapshot)

    @app.get("/v1/runs/{run_id}/trace")
    async def get_run_trace(run_id: str, request: Request) -> dict:
        try:
            record = await _runtime(request).get_record(run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=exc.to_dict()) from exc
        if record.result is None:
            return {"spans": [], "metrics": {}}
        return {
            "spans": record.result.trace.get("spans", []),
            "metrics": record.result.trace.get("metrics", {}),
        }

    @app.post("/v1/runs/{run_id}/resume", response_model=RunResponse)
    async def resume_run(
        run_id: str,
        req: ResumeRunRequest,
        request: Request,
    ) -> RunResponse:
        try:
            snapshot = await _runtime(request).resume(run_id, req.payload)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=exc.to_dict()) from exc
        except InvalidRunStateError as exc:
            raise HTTPException(status_code=409, detail=exc.to_dict()) from exc
        return RunResponse.from_snapshot(snapshot)

    @app.get("/v1/runs/{run_id}/events")
    async def run_events(run_id: str, request: Request) -> StreamingResponse:
        runtime = _runtime(request)

        async def event_generator() -> AsyncIterator[str]:
            try:
                events = await runtime.get_events(run_id)
            except RunNotFoundError as exc:
                yield _sse({"error": exc.to_dict(), "done": True})
                return
            for event in events:
                yield (
                    f"id: {event.sequence}\n"
                    f"event: {event.type}\n"
                    f"data: {event.model_dump_json()}\n\n"
                )

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return app


def _runtime(request: Request) -> RunManager:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="runtime is not ready")
    return runtime


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=18084)
