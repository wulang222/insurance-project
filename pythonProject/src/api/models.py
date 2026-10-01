"""Pydantic contracts for the legacy Chat API and durable Run API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from harness.runtime import RunSnapshot


class ChatRequest(BaseModel):
    session_id: str = Field(
        default="",
        description="Conversation ID. Empty means create a new session.",
    )
    user_id: str | None = Field(default=None, description="User ID.")
    message: str = Field(min_length=1, description="User message.")


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    content: str
    handled_by: str = ""
    route: str = ""
    route_reason: str = ""


class CreateRunRequest(BaseModel):
    message: str = Field(min_length=1)
    user_id: str | None = None
    thread_id: str | None = None
    request_id: str | None = None


class ResumeRunRequest(BaseModel):
    payload: Any


class RunResponse(BaseModel):
    request_id: str
    run_id: str
    thread_id: str
    status: str
    answer: str = ""
    handled_by: list[str] = Field(default_factory=list)
    structured_data: dict[str, Any] = Field(default_factory=dict)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    required_input: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None
    trace: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_snapshot(cls, snapshot: RunSnapshot) -> "RunResponse":
        result = snapshot.result
        if result is None:
            return cls(
                request_id=snapshot.request_id,
                run_id=snapshot.run_id,
                thread_id=snapshot.thread_id,
                status=snapshot.status,
            )
        return cls(
            request_id=snapshot.request_id,
            run_id=snapshot.run_id,
            thread_id=snapshot.thread_id,
            status=snapshot.status,
            answer=result.answer,
            handled_by=result.handled_by,
            structured_data=result.structured_data,
            citations=[item.model_dump(mode="json") for item in result.citations],
            required_input=(
                result.required_input.model_dump(
                    mode="json",
                    exclude_none=True,
                    by_alias=True,
                )
                if result.required_input
                else None
            ),
            warnings=result.warnings,
            error=result.error,
            trace=result.trace,
        )
