"""Typed harness failures with stable machine-readable error codes."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    INPUT_REQUIRED = "INPUT_REQUIRED"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TOOL_INVALID_ARGUMENTS = "TOOL_INVALID_ARGUMENTS"
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    MODEL_INVALID_OUTPUT = "MODEL_INVALID_OUTPUT"
    POLICY_DENIED = "POLICY_DENIED"
    NO_BUSINESS_RESULT = "NO_BUSINESS_RESULT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AgentError(Exception):
    """Base exception that is safe to map into an API error envelope."""

    default_code = ErrorCode.INTERNAL_ERROR

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details = details or {}
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
        }


class ToolExecutionError(AgentError):
    """A tool rejected arguments, timed out, or failed during execution."""

    default_code = ErrorCode.TOOL_INVALID_ARGUMENTS


class DependencyUnavailableError(AgentError):
    """A required database, model provider, or vector store is unavailable."""

    default_code = ErrorCode.DEPENDENCY_UNAVAILABLE


class PolicyDeniedError(AgentError):
    """A policy or authorization rule denied the requested operation."""

    default_code = ErrorCode.POLICY_DENIED


class InvalidAgentOutputError(AgentError):
    """A model or agent returned data that violates its output contract."""

    default_code = ErrorCode.MODEL_INVALID_OUTPUT
