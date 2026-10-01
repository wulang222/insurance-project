"""Durable run orchestration and interrupt/resume protocol."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field

from harness.context import RunContext
from harness.errors import AgentError, ErrorCode
from harness.result import AgentResult, Citation, RequiredInput


RunStatus = Literal["created", "running", "needs_input", "completed", "failed"]
RUN_NAMESPACE = ("harness", "runs")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int
    type: str
    timestamp: str = Field(default_factory=_now)
    data: dict[str, Any] = Field(default_factory=dict)


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: RunContext
    status: RunStatus
    result: AgentResult | None = None
    events: list[RunEvent] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class RunSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    run_id: str
    thread_id: str
    status: RunStatus
    result: AgentResult | None = None

    @classmethod
    def from_record(cls, record: RunRecord) -> "RunSnapshot":
        return cls(
            request_id=record.context.request_id,
            run_id=record.context.run_id,
            thread_id=record.context.thread_id,
            status=record.status,
            result=record.result,
        )


class RunNotFoundError(AgentError):
    pass


class InvalidRunStateError(AgentError):
    pass


class RunManager:
    """Run a compiled graph while persisting identity, status, and events."""

    def __init__(
        self,
        graph: Any,
        store: Any,
        *,
        prompt_version: str = "v1",
        model_policy: str = "balanced",
    ) -> None:
        self.graph = graph
        self.store = store
        self.prompt_version = prompt_version
        self.model_policy = model_policy

    async def start(
        self,
        message: str,
        *,
        user_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ) -> RunSnapshot:
        context = RunContext(
            request_id=request_id or str(uuid.uuid4()),
            run_id=str(uuid.uuid4()),
            thread_id=thread_id or str(uuid.uuid4()),
            user_id=user_id,
            prompt_version=self.prompt_version,
            model_policy=self.model_policy,
        )
        record = RunRecord(context=context, status="created")
        await self._save(record)
        input_data: dict[str, Any] = {
            "messages": [{"role": "user", "content": message}]
        }
        if user_id:
            input_data["user_id"] = user_id
        return await self._execute(record, input_data, resumed=False)

    async def resume(self, run_id: str, payload: Any) -> RunSnapshot:
        record = await self._load(run_id)
        if record.status != "needs_input":
            raise InvalidRunStateError(
                f"run {run_id} is {record.status}, expected needs_input",
                details={"run_id": run_id, "status": record.status},
            )
        self._append_event(record, "run.resumed", {"run_id": run_id})
        return await self._execute(record, Command(resume=payload), resumed=True)

    async def get(self, run_id: str) -> RunSnapshot:
        return RunSnapshot.from_record(await self._load(run_id))

    async def get_events(self, run_id: str) -> list[RunEvent]:
        return list((await self._load(run_id)).events)

    async def _execute(
        self,
        record: RunRecord,
        graph_input: dict[str, Any] | Command,
        *,
        resumed: bool,
    ) -> RunSnapshot:
        record.status = "running"
        record.updated_at = _now()
        if not resumed:
            self._append_event(
                record,
                "run.started",
                {
                    "request_id": record.context.request_id,
                    "run_id": record.context.run_id,
                    "thread_id": record.context.thread_id,
                },
            )
        await self._save(record)

        config = {
            "configurable": {
                "thread_id": record.context.thread_id,
                "run_id": record.context.run_id,
                "request_id": record.context.request_id,
                "scopes": [
                    "insurance:read",
                    "knowledge:read",
                    "crm:read",
                    "memory:write",
                ],
                "max_tool_calls": 20,
                "max_model_calls": 12,
            }
        }
        if record.context.user_id:
            config["configurable"]["user_id"] = record.context.user_id

        try:
            output = await self.graph.ainvoke(graph_input, config)
            interrupts = output.get("__interrupt__", ()) if isinstance(output, dict) else ()
            if interrupts:
                required = self._required_input(interrupts[0])
                record.status = "needs_input"
                record.result = AgentResult(
                    status="needs_input",
                    answer=required.question,
                    handled_by=self._handled_by(output),
                    required_input=required,
                    trace=self._trace(record),
                )
                self._append_event(
                    record,
                    "run.interrupted",
                    required.model_dump(exclude_none=True, by_alias=True),
                )
            else:
                record.status = "completed"
                record.result = self._completed_result(record, output)
                route = output.get("route") if isinstance(output, dict) else None
                if route:
                    self._append_event(record, "route.selected", {"route": route})
                for agent_name in record.result.handled_by:
                    self._append_event(
                        record,
                        "agent.completed",
                        {"agent": agent_name},
                    )
                self._append_event(record, "run.completed", {})
        except Exception as exc:
            error = self._error_payload(exc)
            record.status = "failed"
            record.result = AgentResult(
                status="failed",
                error=error,
                trace=self._trace(record),
            )
            self._append_event(record, "run.failed", error)

        record.updated_at = _now()
        await self._save(record)
        return RunSnapshot.from_record(record)

    def _completed_result(self, record: RunRecord, output: Any) -> AgentResult:
        data = output if isinstance(output, dict) else {}
        answer = (
            data.get("final_answer")
            or data.get("final_recommendation")
            or data.get("crm_report")
            or self._last_message(data)
        )
        structured_data = {
            key: data[key]
            for key in ("route", "route_reason")
            if key in data
        }
        citations = [Citation.model_validate(item) for item in data.get("citations", [])]
        return AgentResult(
            status="completed",
            answer=str(answer or ""),
            handled_by=self._handled_by(data),
            structured_data=structured_data,
            citations=citations,
            trace=self._trace(record),
        )

    @staticmethod
    def _required_input(interrupt_value: Any) -> RequiredInput:
        payload = getattr(interrupt_value, "value", interrupt_value)
        if not isinstance(payload, dict):
            payload = {
                "type": "input_required",
                "fields": ["additional_information"],
                "question": str(payload),
            }
        question = str(payload.get("question") or payload.get("prompt") or "请补充信息")
        fields = payload.get("fields") or ["additional_information"]
        return RequiredInput(
            type=str(payload.get("type", "input_required")),
            fields=[str(field) for field in fields],
            question=question,
            prompt=question,
            reason=payload.get("reason"),
            schema=payload.get("schema", {}),
        )

    @staticmethod
    def _handled_by(output: dict[str, Any]) -> list[str]:
        value = output.get("handled_by", [])
        if isinstance(value, str):
            return [value] if value else []
        return [str(item) for item in value]

    @staticmethod
    def _last_message(output: dict[str, Any]) -> str:
        messages = output.get("messages", [])
        if not messages:
            return ""
        message = messages[-1]
        if isinstance(message, dict):
            return str(message.get("content", ""))
        return str(getattr(message, "content", ""))

    @staticmethod
    def _error_payload(exc: Exception) -> dict[str, Any]:
        if isinstance(exc, AgentError):
            return exc.to_dict()
        return {
            "code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "details": {},
            "retryable": False,
        }

    @staticmethod
    def _trace(record: RunRecord) -> dict[str, str]:
        return {
            "request_id": record.context.request_id,
            "run_id": record.context.run_id,
            "thread_id": record.context.thread_id,
        }

    @staticmethod
    def _append_event(record: RunRecord, event_type: str, data: dict[str, Any]) -> None:
        record.events.append(
            RunEvent(sequence=len(record.events) + 1, type=event_type, data=data)
        )

    async def _save(self, record: RunRecord) -> None:
        await self.store.aput(
            RUN_NAMESPACE,
            record.context.run_id,
            record.model_dump(mode="json", by_alias=True),
        )

    async def _load(self, run_id: str) -> RunRecord:
        item = await self.store.aget(RUN_NAMESPACE, run_id)
        if item is None:
            raise RunNotFoundError(
                f"run {run_id} was not found",
                details={"run_id": run_id},
            )
        value = item.value if hasattr(item, "value") else item["value"]
        return RunRecord.model_validate(value)
