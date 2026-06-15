"""FastAPI entrypoint for the supervisor agent.

The server does not route between business agents. It only exposes an HTTP
interface and delegates every request to the supervisor agent, which is
responsible for child-agent coordination.
"""

from __future__ import annotations

import logging
import json
import sys
import uuid
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from supervisor_agent.graph import build_graph as build_supervisor_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Insurance AI Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supervisor_graph = build_supervisor_graph()


class ChatRequest(BaseModel):
    session_id: str = Field(
        default="", description="Conversation ID. Empty means create a new session."
    )
    user_id: Optional[str] = Field(default=None, description="User ID.")
    message: str = Field(..., description="User message.")


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    content: str
    handled_by: str = ""
    route: str = ""
    route_reason: str = ""


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent": "supervisor_agent"}


@app.post("/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    """Invoke the supervisor agent for one user message."""
    session_id = req.session_id or str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    config = {"configurable": {"thread_id": session_id}}
    input_data = {"messages": [{"role": "user", "content": req.message}]}

    if req.user_id:
        config["configurable"]["user_id"] = req.user_id
        input_data["user_id"] = req.user_id

    try:
        result = await supervisor_graph.ainvoke(input_data, config)
        return ChatResponse(
            session_id=session_id,
            message_id=message_id,
            content=result.get("final_answer", ""),
            handled_by=result.get("handled_by", ""),
            route=result.get("route", ""),
            route_reason=result.get("route_reason", ""),
        )
    except Exception as exc:
        logger.error("Supervisor agent invocation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Stream supervisor agent output as SSE."""
    session_id = req.session_id or str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    config = {"configurable": {"thread_id": session_id}}
    input_data = {"messages": [{"role": "user", "content": req.message}]}

    if req.user_id:
        config["configurable"]["user_id"] = req.user_id
        input_data["user_id"] = req.user_id

    async def event_generator() -> AsyncIterator[str]:
        full_content = ""
        handled_by = ""
        route = ""
        route_reason = ""

        try:
            async for chunk in supervisor_graph.astream(
                input_data, config, stream_mode="values"
            ):
                handled_by = chunk.get("handled_by", handled_by)
                route = chunk.get("route", route)
                route_reason = chunk.get("route_reason", route_reason)

                content = chunk.get("final_answer", "")
                if content and len(content) > len(full_content):
                    delta = content[len(full_content) :]
                    full_content = content
                    yield _sse(
                        {
                            "session_id": session_id,
                            "message_id": message_id,
                            "delta": delta,
                            "handled_by": handled_by,
                            "route": route,
                            "route_reason": route_reason,
                        }
                    )

            yield _sse(
                {
                    "session_id": session_id,
                    "message_id": message_id,
                    "delta": "",
                    "done": True,
                    "handled_by": handled_by,
                    "route": route,
                    "route_reason": route_reason,
                }
            )
        except Exception as exc:
            logger.error("Supervisor agent stream failed: %s", exc, exc_info=True)
            yield _sse({"error": str(exc), "done": True})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=18084)
