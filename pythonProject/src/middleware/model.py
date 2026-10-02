"""Governed model gateway with prompt versioning, budgets and observability."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import time
from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from harness.errors import (
    DependencyUnavailableError,
    ErrorCode,
    InvalidAgentOutputError,
    PolicyDeniedError,
)
from prompts.registry import PromptRegistry
from observability.telemetry import Observability, get_observability, hash_user_id


ModelStrategy = Literal[
    "route", "classify", "extract", "recommend", "aggregate", "compliance", "evaluate"
]


class ModelCallContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    user_id: str | None = None
    max_model_calls: int = Field(default=8, ge=0)
    model_policy: str = "balanced"
    prompt_versions: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "ModelCallContext":
        values = (config or {}).get("configurable", {})
        return cls(
            request_id=str(values.get("request_id", "local-request")),
            run_id=str(values.get("run_id", values.get("thread_id", "local-run"))),
            user_id=values.get("user_id"),
            max_model_calls=int(values.get("max_model_calls", 8)),
            model_policy=str(values.get("model_policy", "balanced")),
            prompt_versions=dict(values.get("prompt_versions", {})),
        )


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    prompt_id: str
    prompt_version: str = "v1"
    variables: dict[str, Any] = Field(default_factory=dict)
    strategy: ModelStrategy
    response_model: Any = str
    timeout_seconds: float = Field(default=30.0, gt=0)


class ModelResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    data: Any
    raw_text: str
    model_name: str
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    repaired: bool = False
    fallback_used: bool = False


class ModelAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    run_id: str
    model_name: str
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    status: Literal["ok", "timeout", "invalid", "failed", "budget_exceeded"]
    repaired: bool = False
    fallback_used: bool = False


class ModelGateway:
    """Only supported production path to an LLM provider."""

    _TEMPERATURES: dict[ModelStrategy, float] = {
        "route": 0.0,
        "classify": 0.0,
        "extract": 0.0,
        "recommend": 0.3,
        "aggregate": 0.2,
        "compliance": 0.0,
        "evaluate": 0.0,
    }

    def __init__(
        self,
        llm_factory: Any,
        prompt_registry: PromptRegistry,
        *,
        primary_model: str | None = None,
        fallback_model: str | None = None,
        low_cost_model: str | None = None,
        stable_model: str | None = None,
        max_retries: int = 2,
        base_backoff_seconds: float = 0.05,
        observability: Observability | None = None,
    ) -> None:
        self.llm_factory = llm_factory
        self.prompt_registry = prompt_registry
        self.primary_model = primary_model or os.getenv("MODEL_PRIMARY", "qwen3.7-plus")
        self.fallback_model = fallback_model or os.getenv("MODEL_FALLBACK", "qwen-plus")
        self.low_cost_model = low_cost_model or os.getenv("MODEL_LOW_COST", self.fallback_model)
        self.stable_model = stable_model or os.getenv("MODEL_STABLE", self.primary_model)
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self.audit_events: list[ModelAuditEvent] = []
        self._call_counts: defaultdict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        self.observability = observability or get_observability()

    async def invoke(
        self,
        request: ModelRequest,
        *,
        context: ModelCallContext,
    ) -> ModelResult:
        request = request.model_copy(
            update={
                "prompt_version": self._resolve_prompt_version(
                    request.prompt_id,
                    request.prompt_version,
                    context.prompt_versions,
                )
            }
        )
        safe_variables = self._redact_prompt_variables(request.variables)
        rendered = self.prompt_registry.render(
            request.prompt_id,
            request.prompt_version,
            safe_variables,
        )
        started = time.perf_counter()
        status = "failed"
        model_name = self._select_model(request.strategy, context.model_policy)
        input_tokens = self._estimate_tokens(rendered.text)
        output_tokens = 0
        repaired = False
        fallback_used = False
        retry_count = 0
        span_scope = self.observability.span(
            "invoke_model",
            {
                "run.id": context.run_id,
                "user.id_hash": hash_user_id(context.user_id),
                "prompt.id": request.prompt_id,
                "prompt.version": request.prompt_version,
                "model.name": model_name,
                "model.policy": context.model_policy,
            },
        )
        span = span_scope.__enter__()
        try:
            response, model_name, fallback_used, retry_count = await self._call_with_policy(
                rendered.text,
                request,
                context,
            )
            raw_text = self._response_text(response)
            input_tokens, output_tokens = self._usage(response, rendered.text, raw_text)
            try:
                data = self._validate_output(raw_text, request.response_model)
            except (json.JSONDecodeError, ValidationError, ValueError):
                if request.response_model is str:
                    raise
                repaired = True
                repair_text = (
                    "修复下面的输出，使其成为严格符合给定 JSON 输出契约的 JSON。"
                    "只返回 JSON，不要解释。\n"
                    f"原输出：{raw_text}\n"
                    f"输出契约：{json.dumps(self._schema(request.response_model), ensure_ascii=False)}"
                )
                repair_response, model_name, repair_fallback, repair_retries = await self._call_with_policy(
                    repair_text,
                    request,
                    context,
                )
                fallback_used = fallback_used or repair_fallback
                retry_count += repair_retries
                raw_text = self._response_text(repair_response)
                repair_in, repair_out = self._usage(repair_response, repair_text, raw_text)
                input_tokens += repair_in
                output_tokens += repair_out
                try:
                    data = self._validate_output(raw_text, request.response_model)
                except (json.JSONDecodeError, ValidationError, ValueError) as repair_exc:
                    status = "invalid"
                    raise InvalidAgentOutputError(
                        "model output remained invalid after one repair",
                        details={"prompt_id": request.prompt_id},
                    ) from repair_exc
            self._compliance_precheck(raw_text)

            status = "ok"
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            return ModelResult(
                data=data,
                raw_text=raw_text,
                model_name=model_name,
                prompt_id=rendered.prompt_id,
                prompt_version=rendered.prompt_version,
                prompt_hash=rendered.prompt_hash,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
                repaired=repaired,
                fallback_used=fallback_used,
            )
        except PolicyDeniedError:
            status = "budget_exceeded"
            raise
        except InvalidAgentOutputError:
            status = "invalid"
            raise
        except TimeoutError as exc:
            status = "timeout"
            raise DependencyUnavailableError(
                "model request timed out",
                code=ErrorCode.MODEL_TIMEOUT,
                details={"model": model_name},
                retryable=True,
            ) from exc
        finally:
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            self.audit_events.append(
                ModelAuditEvent(
                    request_id=context.request_id,
                    run_id=context.run_id,
                    model_name=model_name,
                    prompt_id=rendered.prompt_id,
                    prompt_version=rendered.prompt_version,
                    prompt_hash=rendered.prompt_hash,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_ms=duration_ms,
                    status=status,
                    repaired=repaired,
                    fallback_used=fallback_used,
                )
            )
            self.observability.metrics.increment("model_call_total")
            self.observability.metrics.increment(
                "model_tokens_total",
                input_tokens + output_tokens,
            )
            span.set_attribute("model.name", model_name)
            span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
            span.set_attribute("duration_ms", duration_ms)
            span.set_attribute("retry_count", retry_count)
            span.set_attribute("fallback_used", fallback_used)
            span.set_attribute("status", status)
            if status != "ok":
                span.error_type = status
            span_scope.__exit__(None, None, None)

    async def _call_with_policy(
        self,
        prompt: str,
        request: ModelRequest,
        context: ModelCallContext,
    ) -> tuple[Any, str, bool, int]:
        last_error: Exception | None = None
        selected_model = self._select_model(request.strategy, context.model_policy)
        models = [selected_model]
        fallback_candidate = (
            self.fallback_model
            if self.fallback_model != selected_model
            else self.primary_model
        )
        if fallback_candidate != selected_model:
            models.append(fallback_candidate)
        for model_index, model_name in enumerate(models):
            for retry in range(self.max_retries + 1):
                await self._consume_budget(context)
                try:
                    llm = self._create_model(model_name, self._TEMPERATURES[request.strategy])
                    response = await asyncio.wait_for(
                        self._invoke_model(llm, prompt),
                        timeout=request.timeout_seconds,
                    )
                    retry_count = model_index * (self.max_retries + 1) + retry
                    return response, model_name, model_index > 0, retry_count
                except PolicyDeniedError:
                    raise
                except Exception as exc:
                    if not self._is_transient(exc):
                        raise
                    last_error = exc
                    if retry < self.max_retries:
                        await asyncio.sleep(self.base_backoff_seconds * (2**retry))
            # Only transient failures reach the fallback model.
        if isinstance(last_error, TimeoutError):
            raise last_error
        raise DependencyUnavailableError(
            "all configured model providers are unavailable",
            details={"primary": self.primary_model, "fallback": self.fallback_model},
            retryable=True,
        ) from last_error

    async def _consume_budget(self, context: ModelCallContext) -> None:
        async with self._lock:
            if self._call_counts[context.run_id] >= context.max_model_calls:
                raise PolicyDeniedError(
                    "model call budget exceeded",
                    details={"run_id": context.run_id, "limit": context.max_model_calls},
                )
            self._call_counts[context.run_id] += 1

    def _create_model(self, model_name: str, temperature: float) -> Any:
        try:
            return self.llm_factory(model=model_name, temperature=temperature)
        except TypeError:
            return self.llm_factory(temperature=temperature)

    def _select_model(self, strategy: ModelStrategy, policy: str = "balanced") -> str:
        if policy == "cheap":
            return self.low_cost_model
        if policy == "stable":
            return self.stable_model
        if strategy in ("route", "classify", "extract"):
            return self.low_cost_model
        if strategy in ("compliance", "evaluate"):
            return self.stable_model
        return self.primary_model

    @staticmethod
    def _resolve_prompt_version(
        prompt_id: str,
        default: str,
        overrides: dict[str, str],
    ) -> str:
        if prompt_id in overrides:
            return overrides[prompt_id]
        namespace = prompt_id.split(".", 1)[0]
        return overrides.get(namespace, overrides.get("*", default))

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        if isinstance(exc, (TimeoutError, OSError, ConnectionError)):
            return True
        status_code = getattr(exc, "status_code", None)
        return status_code == 429 or (isinstance(status_code, int) and status_code >= 500)

    @staticmethod
    async def _invoke_model(llm: Any, prompt: str) -> Any:
        if hasattr(llm, "ainvoke"):
            return await llm.ainvoke(prompt)
        result = llm.invoke(prompt)
        if inspect.isawaitable(result):
            return await result
        return result

    @classmethod
    def _validate_output(cls, raw_text: str, response_model: Any) -> Any:
        if response_model is str:
            return raw_text
        parsed = json.loads(cls._extract_json(raw_text))
        return TypeAdapter(response_model).validate_python(parsed)

    @staticmethod
    def _extract_json(text: str) -> str:
        stripped = text.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
        if fenced:
            stripped = fenced.group(1)
        starts = [index for index in (stripped.find("{"), stripped.find("[")) if index >= 0]
        if starts:
            start = min(starts)
            end = max(stripped.rfind("}"), stripped.rfind("]"))
            if end >= start:
                return stripped[start : end + 1]
        return stripped

    @staticmethod
    def _response_text(response: Any) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, list):
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return str(content)

    @classmethod
    def _usage(cls, response: Any, prompt: str, output: str) -> tuple[int, int]:
        usage = getattr(response, "usage_metadata", None) or {}
        input_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
        output_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
        return (
            input_tokens or cls._estimate_tokens(prompt),
            output_tokens or cls._estimate_tokens(output),
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4) if text else 0

    @staticmethod
    def _schema(response_model: Any) -> dict[str, Any]:
        try:
            return TypeAdapter(response_model).json_schema()
        except Exception:
            return {"type": "object"}

    @classmethod
    def _redact_prompt_variables(cls, value: Any, key: str = "") -> Any:
        secret_keys = {"password", "token", "api_key", "id_card", "phone", "mobile"}
        if key.lower() in secret_keys:
            return "***REDACTED***"
        if isinstance(value, dict):
            return {item_key: cls._redact_prompt_variables(item, item_key) for item_key, item in value.items()}
        if isinstance(value, list):
            return [cls._redact_prompt_variables(item) for item in value]
        if isinstance(value, str):
            value = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "***PHONE***", value)
            return re.sub(r"(?<!\d)\d{17}[0-9Xx](?!\d)", "***ID***", value)
        return value

    @staticmethod
    def _compliance_precheck(raw_text: str) -> None:
        # Fail closed if a provider leaks credential-like material into an answer.
        if re.search(r"(?:api[_-]?key|password)\s*[:=]\s*\S+", raw_text, re.IGNORECASE):
            raise InvalidAgentOutputError("model output failed compliance precheck")
