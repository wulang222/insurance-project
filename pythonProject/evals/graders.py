"""Deterministic graders and report contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Grade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    score: float = Field(ge=0, le=1)
    reason: str
    review_required: bool = False


def exact_match(name: str, actual: object, expected: object) -> Grade:
    passed = actual == expected
    return Grade(
        name=name,
        passed=passed,
        score=1.0 if passed else 0.0,
        reason=f"expected={expected!r}; actual={actual!r}",
    )


def required_subset(name: str, actual: list[str], required: list[str]) -> Grade:
    missing = sorted(set(required) - set(actual))
    return Grade(
        name=name,
        passed=not missing,
        score=1.0 if not missing else max(0.0, 1 - len(missing) / max(1, len(required))),
        reason="all required values present" if not missing else f"missing={missing}",
    )


def forbidden_absent(name: str, actual: list[str], forbidden: list[str]) -> Grade:
    found = sorted(set(actual) & set(forbidden))
    return Grade(
        name=name,
        passed=not found,
        score=1.0 if not found else 0.0,
        reason="no forbidden values" if not found else f"found={found}",
    )


def human_sample_grade(case_id: str, answer: str) -> Grade:
    """Flag model-style quality dimensions for mandatory human sampling."""

    readable = bool(answer.strip()) and len(answer) <= 4000
    return Grade(
        name="model_quality_human_sample",
        passed=readable,
        score=1.0 if readable else 0.0,
        reason=f"case={case_id}; automated precheck only; human review required",
        review_required=True,
    )
