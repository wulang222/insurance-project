"""Safe trace hierarchy and metrics used by the harness and replay tools."""

from __future__ import annotations

import contextvars
import hashlib
import os
import threading
import time
import uuid
from collections import defaultdict
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel, ConfigDict, Field


REQUIRED_METRICS = (
    "agent_run_total",
    "agent_run_duration_seconds",
    "agent_run_failed_total",
    "model_call_total",
    "model_tokens_total",
    "tool_call_total",
    "tool_call_failed_total",
    "interrupt_total",
    "compliance_reject_total",
    "rag_no_evidence_total",
)

_SAFE_ATTRIBUTES = {
    "run.id",
    "thread.id",
    "user.id_hash",
    "agent.name",
    "agent.version",
    "prompt.id",
    "prompt.version",
    "model.name",
    "model.policy",
    "tool.name",
    "tool.version",
    "tool.risk_level",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "duration_ms",
    "retry_count",
    "fallback_used",
    "error.type",
    "status",
    "route",
}

_current_span_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "observability_current_span_id",
    default=None,
)
_provider_lock = threading.Lock()
_provider_configured = False


def _utc_from_ns(value: int) -> str:
    return datetime.fromtimestamp(value / 1_000_000_000, tz=timezone.utc).isoformat()


def hash_user_id(user_id: str | None) -> str | None:
    if not user_id:
        return None
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]


class SpanRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    span_id: str
    parent_span_id: str | None = None
    name: str
    start_time: str
    end_time: str
    duration_ms: int = Field(ge=0)
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)
    status: str
    error_type: str | None = None


class MetricsRegistry:
    """Small dependency-free metric store suitable for tests and JSON export."""

    def __init__(self) -> None:
        self._counters: defaultdict[str, float] = defaultdict(float)
        self._histograms: defaultdict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        for name in REQUIRED_METRICS:
            self._counters[name] = 0.0

    def increment(self, name: str, value: float = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            self._histograms[name].append(float(value))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = dict(self._counters)
            histograms = {
                name: {
                    "count": len(values),
                    "sum": sum(values),
                    "min": min(values),
                    "max": max(values),
                }
                for name, values in self._histograms.items()
                if values
            }
        # Duration is a histogram but remains visible even before the first run.
        histograms.setdefault(
            "agent_run_duration_seconds",
            {"count": 0, "sum": 0.0, "min": 0.0, "max": 0.0},
        )
        counters.pop("agent_run_duration_seconds", None)
        return {"counters": counters, "histograms": histograms}


class _SpanHandle:
    def __init__(self, attributes: dict[str, Any], otel_span: Any) -> None:
        self.attributes = attributes
        self.otel_span = otel_span
        self.error_type: str | None = None

    def set_attribute(self, key: str, value: Any) -> None:
        safe = _safe_attributes({key: value})
        if key not in safe:
            return
        self.attributes[key] = safe[key]
        self.otel_span.set_attribute(key, safe[key])


class Observability:
    """Records OpenTelemetry spans plus a bounded serializable replay view."""

    def __init__(self, *, service_name: str = "insurance-agent", max_spans: int = 5000) -> None:
        _ensure_otel_provider(service_name)
        self.service_name = service_name
        self.max_spans = max_spans
        self.metrics = MetricsRegistry()
        self._tracer = trace.get_tracer(service_name)
        self._spans: list[SpanRecord] = []
        self._lock = threading.Lock()

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, Any] | None = None) -> Iterator[_SpanHandle]:
        safe = _safe_attributes(attributes or {})
        span_id = uuid.uuid4().hex[:16]
        parent_span_id = _current_span_id.get()
        start_ns = time.time_ns()
        token = _current_span_id.set(span_id)
        error_type: str | None = None
        with self._tracer.start_as_current_span(name, attributes=safe) as otel_span:
            handle = _SpanHandle(safe, otel_span)
            try:
                yield handle
            except Exception as exc:
                error_type = type(exc).__name__
                handle.error_type = error_type
                handle.set_attribute("error.type", error_type)
                otel_span.set_status(Status(StatusCode.ERROR, error_type))
                raise
            finally:
                error_type = error_type or handle.error_type
                if error_type:
                    otel_span.set_status(Status(StatusCode.ERROR, error_type))
                end_ns = time.time_ns()
                _current_span_id.reset(token)
                self._append_span(
                    SpanRecord(
                        span_id=span_id,
                        parent_span_id=parent_span_id,
                        name=name,
                        start_time=_utc_from_ns(start_ns),
                        end_time=_utc_from_ns(end_ns),
                        duration_ms=max(0, int((end_ns - start_ns) / 1_000_000)),
                        attributes=safe,
                        status="error" if error_type else "ok",
                        error_type=error_type,
                    )
                )

    def record_completed_span(
        self,
        name: str,
        *,
        start_ns: int,
        end_ns: int,
        attributes: Mapping[str, Any],
        status: str = "ok",
    ) -> None:
        safe = _safe_attributes(attributes)
        parent_span_id = _current_span_id.get()
        otel_span = self._tracer.start_span(name, attributes=safe, start_time=start_ns)
        if status != "ok":
            otel_span.set_status(Status(StatusCode.ERROR, status))
        otel_span.end(end_time=end_ns)
        self._append_span(
            SpanRecord(
                span_id=uuid.uuid4().hex[:16],
                parent_span_id=parent_span_id,
                name=name,
                start_time=_utc_from_ns(start_ns),
                end_time=_utc_from_ns(end_ns),
                duration_ms=max(0, int((end_ns - start_ns) / 1_000_000)),
                attributes=safe,
                status=status,
                error_type=None if status == "ok" else status,
            )
        )

    def start_span(self, name: str, **attributes: Any):
        """Protocol-compatible alias used by injected Agent dependencies."""

        return self.span(name, attributes)

    def cursor(self) -> int:
        with self._lock:
            return len(self._spans)

    def spans_since(self, cursor: int, *, run_id: str | None = None) -> list[SpanRecord]:
        with self._lock:
            values = list(self._spans[cursor:])
        if run_id is not None:
            values = [item for item in values if item.attributes.get("run.id") == run_id]
        return values

    def snapshot(self, *, run_id: str | None = None) -> dict[str, Any]:
        spans = self.spans_since(0, run_id=run_id)
        return {
            "spans": [item.model_dump(mode="json") for item in spans],
            "metrics": self.metrics.snapshot(),
        }

    def _append_span(self, span: SpanRecord) -> None:
        with self._lock:
            self._spans.append(span)
            overflow = len(self._spans) - self.max_spans
            if overflow > 0:
                del self._spans[:overflow]


def _safe_attributes(values: Mapping[str, Any]) -> dict[str, str | int | float | bool]:
    safe: dict[str, str | int | float | bool] = {}
    for key, value in values.items():
        if key not in _SAFE_ATTRIBUTES or value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            safe[key] = value
        else:
            safe[key] = str(value)
    return safe


def _ensure_otel_provider(service_name: str) -> None:
    """Install the SDK once; attach OTLP export only when explicitly configured."""

    global _provider_configured
    with _provider_lock:
        if _provider_configured:
            return
        current = trace.get_tracer_provider()
        if hasattr(current, "add_span_processor"):
            _provider_configured = True
            return
        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name})
        )
        if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)
        _provider_configured = True


_DEFAULT_OBSERVABILITY = Observability()


def get_observability() -> Observability:
    return _DEFAULT_OBSERVABILITY
