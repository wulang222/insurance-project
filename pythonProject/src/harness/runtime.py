"""Durable run orchestration and interrupt/resume protocol."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field

from harness.context import RunContext
from harness.errors import AgentError, ErrorCode
from harness.result import AgentResult, Citation, RequiredInput
from observability.telemetry import Observability, get_observability, hash_user_id


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
    replay_input: dict[str, Any] = Field(default_factory=dict)
    parent_run_id: str | None = None


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
        observability: Observability | None = None,
    ) -> None:
        self.graph = graph
        self.store = store
        self.prompt_version = prompt_version
        self.model_policy = model_policy
        self.observability = observability or get_observability()

    async def start(
        self,
        message: str,
        *,
        user_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> RunSnapshot:
        context = RunContext(
            request_id=request_id or str(uuid.uuid4()),
            run_id=str(uuid.uuid4()),
            thread_id=thread_id or str(uuid.uuid4()),
            user_id=user_id,
            prompt_version=self.prompt_version,
            model_policy=self.model_policy,
        )
        record = RunRecord(
            context=context,
            status="created",
            replay_input={"message": message, "user_id": user_id},
            parent_run_id=parent_run_id,
        )
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
        record.replay_input.setdefault("resume_payloads", []).append(payload)
        self._append_event(record, "run.resumed", {"run_id": run_id})
        return await self._execute(record, Command(resume=payload), resumed=True)

    async def get(self, run_id: str) -> RunSnapshot:
        return RunSnapshot.from_record(await self._load(run_id))

    async def get_events(self, run_id: str) -> list[RunEvent]:
        return list((await self._load(run_id)).events)

    async def get_record(self, run_id: str) -> RunRecord:
        """Return the persisted record for observability and replay tooling."""

        return await self._load(run_id)

    async def replay(
        self,
        run_id: str,
        *,
        prompt_version: str | None = None,
        model_policy: str | None = None,
    ) -> RunSnapshot:
        source = await self._load(run_id)
        message = source.replay_input.get("message")
        if not isinstance(message, str) or not message:
            raise InvalidRunStateError(
                f"run {run_id} has no replayable input",
                details={"run_id": run_id},
            )
        replay_manager = RunManager(
            self.graph,
            self.store,
            prompt_version=prompt_version or source.context.prompt_version,
            model_policy=model_policy or source.context.model_policy,
            observability=self.observability,
        )
        snapshot = await replay_manager.start(
            message,
            user_id=source.replay_input.get("user_id"),
            thread_id=f"{source.context.thread_id}:replay:{uuid.uuid4().hex[:8]}",
            parent_run_id=run_id,
        )
        for payload in source.replay_input.get("resume_payloads", []):
            if snapshot.status != "needs_input":
                break
            snapshot = await replay_manager.resume(snapshot.run_id, payload)
        return snapshot

    async def _execute(
        self,
        record: RunRecord,
        graph_input: dict[str, Any] | Command,
        *,
        resumed: bool,
    ) -> RunSnapshot:
        execution_started = time.perf_counter()
        span_scope = self.observability.span(
            f"run {record.context.run_id}",
            {
                "run.id": record.context.run_id,
                "thread.id": record.context.thread_id,
                "user.id_hash": hash_user_id(record.context.user_id),
                "prompt.version": record.context.prompt_version,
                "model.policy": record.context.model_policy,
            },
        )
        run_span = span_scope.__enter__()
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
                    "memory:read",
                    "memory:write",
                ],
                "max_tool_calls": record.context.max_tool_calls,
                "max_model_calls": record.context.max_model_calls,
                "model_policy": record.context.model_policy,
                "prompt_versions": _parse_prompt_versions(record.context.prompt_version),
            }
        }
        if record.context.user_id:
            config["configurable"]["user_id"] = record.context.user_id

        output: Any = {}
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
                self.observability.metrics.increment("interrupt_total")
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

        self._record_graph_spans(output, record)
        child = output.get("child_result", output) if isinstance(output, dict) else {}
        compliance = child.get("compliance", {}) if isinstance(child, dict) else {}
        if compliance and (
            not compliance.get("passed", True) or int(compliance.get("revision_count", 0)) > 0
        ):
            self.observability.metrics.increment("compliance_reject_total")
        if isinstance(child, dict) and "evidence" in child and not child.get("evidence"):
            self.observability.metrics.increment("rag_no_evidence_total")
        duration_seconds = max(0.0, time.perf_counter() - execution_started)
        self.observability.metrics.increment("agent_run_total")
        self.observability.metrics.observe("agent_run_duration_seconds", duration_seconds)
        if record.status == "failed":
            self.observability.metrics.increment("agent_run_failed_total")
            run_span.error_type = str((record.result.error or {}).get("code", "failed"))
        run_span.set_attribute("duration_ms", int(duration_seconds * 1000))
        run_span.set_attribute("status", record.status)
        span_scope.__exit__(None, None, None)

        trace_snapshot = self.observability.snapshot(run_id=record.context.run_id)
        if record.result is not None:
            record.result.trace.update(trace_snapshot)
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
        child_result = data.get("child_result")
        if data.get("route") == "family_plan" and isinstance(child_result, dict):
            structured_data["family_plan"] = {
                key: child_result[key]
                for key in (
                    "plan",
                    "profile",
                    "coverage_gaps",
                    "products",
                    "evidence",
                    "disclaimer",
                    "recommendation_draft",
                    "compliance",
                    "agent_trace",
                )
                if key in child_result
            }
        citation_data = data.get("citations", [])
        if not citation_data and isinstance(child_result, dict):
            citation_data = child_result.get("citations", [])
        citations = [Citation.model_validate(item) for item in citation_data]
        return AgentResult(
            status="completed",
            answer=str(answer or ""),
            handled_by=self._handled_by(data),
            structured_data=structured_data,
            citations=citations,
            warnings=[str(item) for item in data.get("warnings", [])],
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
    def _trace(record: RunRecord) -> dict[str, Any]:
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

    def _record_graph_spans(self, output: Any, record: RunRecord) -> None:
        if not isinstance(output, dict):
            return
        route = output.get("route")
        now_ns = time.time_ns()
        if route:
            self.observability.record_completed_span(
                "route",
                start_ns=now_ns,
                end_ns=now_ns,
                attributes={"run.id": record.context.run_id, "route": route},
            )
        child = output.get("child_result", output)
        if not isinstance(child, dict):
            return
        if child.get("plan"):
            self.observability.record_completed_span(
                "plan",
                start_ns=now_ns,
                end_ns=now_ns,
                attributes={"run.id": record.context.run_id},
            )
        for item in child.get("agent_trace", []):
            duration_ns = max(
                0,
                int(item.get("finished_at_ns", 0)) - int(item.get("started_at_ns", 0)),
            )
            end_ns = time.time_ns()
            agent_name = str(item.get("agent", "unknown"))
            self.observability.record_completed_span(
                f"invoke_agent {agent_name}" if agent_name != "aggregate" else "aggregate",
                start_ns=end_ns - duration_ns,
                end_ns=end_ns,
                attributes={
                    "run.id": record.context.run_id,
                    "agent.name": agent_name,
                    "agent.version": "workflow" if agent_name == "aggregate" else "1.0.0",
                    "status": str(item.get("status", "completed")),
                },
                status="ok" if item.get("status") != "failed" else "failed",
            )


def _parse_prompt_versions(value: str) -> dict[str, str]:
    """Parse `recommendation:v2` or a global `v2` replay override."""

    if ":" in value:
        namespace, version = value.split(":", 1)
        return {namespace: version}
    return {"*": value}
