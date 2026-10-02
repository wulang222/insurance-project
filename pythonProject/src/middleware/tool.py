"""Ordered Tool Gateway middleware with fail-closed policy enforcement."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from harness.errors import (
    AgentError,
    DependencyUnavailableError,
    ErrorCode,
    PolicyDeniedError,
    ToolExecutionError,
)
from harness.result import ToolResult
from observability.telemetry import Observability, get_observability
from tools.base import ToolAuditEvent, ToolCallContext, ToolDefinition
from tools.registry import ToolRegistry


class ToolGateway:
    """The sole production entry point for business tool execution.

    The method body deliberately follows the documented middleware order:
    trace, authentication, authorization, validation, risk, budget,
    timeout/retry, idempotency, execution, output validation, redaction,
    normalization, and audit.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        max_read_attempts: int = 2,
        observability: Observability | None = None,
    ) -> None:
        self.registry = registry
        self.max_read_attempts = max_read_attempts
        self.audit_events: list[ToolAuditEvent] = []
        self._call_counts: defaultdict[str, int] = defaultdict(int)
        self._idempotency_cache: dict[tuple[str, str, str], ToolResult] = {}
        self._lock = asyncio.Lock()
        self.observability = observability or get_observability()

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        context: ToolCallContext,
    ) -> ToolResult:
        started = time.perf_counter()
        definition = self.registry.get(tool_name)
        spec = definition.spec
        status = "failed"
        attempts = 0
        cache_hit = False
        span_scope = self.observability.span(
            f"execute_tool {spec.name}",
            {
                "run.id": context.run_id,
                "user.id_hash": _hash_user(context.user_id),
                "tool.name": spec.name,
                "tool.version": spec.version,
                "tool.risk_level": spec.risk_level,
            },
        )
        span = span_scope.__enter__()
        try:
            # Authentication and authorization are intentionally fail closed.
            if not context.request_id or not context.run_id:
                status = "denied"
                raise PolicyDeniedError("tool caller is not authenticated")
            missing_scopes = set(spec.required_scopes) - set(context.scopes)
            if missing_scopes:
                status = "denied"
                raise PolicyDeniedError(
                    f"missing scopes for {tool_name}",
                    details={"missing_scopes": sorted(missing_scopes)},
                )

            # Arguments are validated before a handler or budget slot is touched.
            try:
                validated_input = definition.input_model.model_validate(arguments)
            except ValidationError as exc:
                status = "invalid"
                raise ToolExecutionError(
                    f"invalid arguments for {tool_name}",
                    details={"errors": exc.errors(include_url=False)},
                ) from exc

            if spec.risk_level == "sensitive" and not context.approved:
                status = "denied"
                raise PolicyDeniedError(
                    f"explicit approval is required for {tool_name}",
                    details={"risk_level": spec.risk_level},
                )

            async with self._lock:
                if self._call_counts[context.run_id] >= context.max_tool_calls:
                    status = "budget_exceeded"
                    raise PolicyDeniedError(
                        "tool call budget exceeded",
                        details={"run_id": context.run_id, "limit": context.max_tool_calls},
                    )
                self._call_counts[context.run_id] += 1

            cache_key = None
            if spec.idempotent and context.idempotency_key:
                cache_key = (context.run_id, tool_name, context.idempotency_key)
                cached = self._idempotency_cache.get(cache_key)
                if cached is not None:
                    cache_hit = True
                    status = "ok"
                    return cached.model_copy(update={"cache_hit": True})

            max_attempts = (
                self.max_read_attempts
                if spec.risk_level == "read" and spec.idempotent
                else 1
            )
            output: Any = None
            for attempt in range(1, max_attempts + 1):
                attempts = attempt
                try:
                    output = await asyncio.wait_for(
                        self._invoke(definition, validated_input, context),
                        timeout=spec.timeout_seconds,
                    )
                    break
                except TimeoutError as exc:
                    if attempt == max_attempts:
                        status = "timeout"
                        raise ToolExecutionError(
                            f"tool {tool_name} timed out",
                            code=ErrorCode.TOOL_TIMEOUT,
                            details={"attempts": attempt},
                            retryable=spec.risk_level == "read" and spec.idempotent,
                        ) from exc
                except DependencyUnavailableError:
                    if attempt == max_attempts:
                        raise

            try:
                validated_output = TypeAdapter(definition.output_model).validate_python(output)
            except ValidationError as exc:
                status = "invalid"
                raise ToolExecutionError(
                    f"invalid output from {tool_name}",
                    details={"errors": exc.errors(include_url=False)},
                ) from exc

            data = self._redact(self._dump(validated_output))
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            result = ToolResult(
                ok=True,
                data=data,
                source=spec.name,
                source_version=spec.version,
                latency_ms=duration_ms,
            )
            if cache_key is not None:
                self._idempotency_cache[cache_key] = result
            status = "ok"
            return result
        except AgentError:
            raise
        except Exception as exc:
            raise ToolExecutionError(
                f"tool {tool_name} failed",
                details={"exception_type": type(exc).__name__},
            ) from exc
        finally:
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            self.audit_events.append(
                ToolAuditEvent(
                    request_id=context.request_id,
                    run_id=context.run_id,
                    tool_name=spec.name,
                    tool_version=spec.version,
                    duration_ms=duration_ms,
                    status=status,
                    attempts=attempts,
                    cache_hit=cache_hit,
                )
            )
            self.observability.metrics.increment("tool_call_total")
            if status != "ok":
                self.observability.metrics.increment("tool_call_failed_total")
                span.error_type = status
            span.set_attribute("duration_ms", duration_ms)
            span.set_attribute("retry_count", max(0, attempts - 1))
            span.set_attribute("status", status)
            span_scope.__exit__(None, None, None)

    @staticmethod
    async def _invoke(
        definition: ToolDefinition,
        value: BaseModel,
        context: ToolCallContext,
    ) -> Any:
        kwargs = value.model_dump()
        if "context" in inspect.signature(definition.handler).parameters:
            kwargs["context"] = context
        result = definition.handler(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    @classmethod
    def _redact(cls, value: Any) -> Any:
        sensitive = {"password", "token", "api_key", "id_card", "phone", "mobile"}
        if isinstance(value, dict):
            return {
                key: "***REDACTED***" if key.lower() in sensitive else cls._redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._redact(item) for item in value]
        return value

    @staticmethod
    def _dump(value: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, list):
            return [ToolGateway._dump(item) for item in value]
        return value


def _hash_user(user_id: str | None) -> str | None:
    if not user_id:
        return None
    import hashlib

    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
