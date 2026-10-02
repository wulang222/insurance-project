"""Replay one persisted run and compare its observable behavior."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from harness.lifecycle import production_lifespan
from harness.runtime import RunRecord


class ReplayComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_run_id: str
    replay_run_id: str
    final_answer: dict[str, str]
    route_and_plan: dict[str, Any]
    tool_calls: dict[str, list[str]]
    citations: dict[str, list[str]]
    compliance: dict[str, Any]
    usage: dict[str, Any]
    estimated_cost: dict[str, float]
    duration_ms: dict[str, int]


def compare_records(source: RunRecord, replayed: RunRecord) -> ReplayComparison:
    return ReplayComparison(
        source_run_id=source.context.run_id,
        replay_run_id=replayed.context.run_id,
        final_answer={"source": _answer(source), "replay": _answer(replayed)},
        route_and_plan={"source": _route_plan(source), "replay": _route_plan(replayed)},
        tool_calls={"source": _tool_calls(source), "replay": _tool_calls(replayed)},
        citations={"source": _citations(source), "replay": _citations(replayed)},
        compliance={"source": _compliance(source), "replay": _compliance(replayed)},
        usage={"source": _usage(source), "replay": _usage(replayed)},
        estimated_cost={"source": _cost(source), "replay": _cost(replayed)},
        duration_ms={"source": _duration(source), "replay": _duration(replayed)},
    )


async def replay_run(run_id: str, *, prompt_version: str | None, model_policy: str | None):
    app = FastAPI()
    async with production_lifespan(app):
        runtime = app.state.runtime
        source = await runtime.get_record(run_id)
        snapshot = await runtime.replay(
            run_id,
            prompt_version=prompt_version,
            model_policy=model_policy,
        )
        replayed = await runtime.get_record(snapshot.run_id)
        return compare_records(source, replayed)


def _trace(record: RunRecord) -> list[dict[str, Any]]:
    return list((record.result.trace if record.result else {}).get("spans", []))


def _answer(record: RunRecord) -> str:
    return record.result.answer if record.result else ""


def _route_plan(record: RunRecord) -> Any:
    data = record.result.structured_data if record.result else {}
    family = data.get("family_plan", {})
    return {"route": data.get("route"), "plan": family.get("plan", [])}


def _tool_calls(record: RunRecord) -> list[str]:
    return [
        str(item["attributes"]["tool.name"])
        for item in _trace(record)
        if "tool.name" in item.get("attributes", {})
    ]


def _citations(record: RunRecord) -> list[str]:
    return [item.citation_id for item in (record.result.citations if record.result else [])]


def _compliance(record: RunRecord) -> Any:
    data = record.result.structured_data if record.result else {}
    return data.get("family_plan", {}).get("compliance")


def _usage(record: RunRecord) -> dict[str, int]:
    model_spans = [item for item in _trace(record) if item["name"] == "invoke_model"]
    return {
        "input_tokens": sum(int(item["attributes"].get("gen_ai.usage.input_tokens", 0)) for item in model_spans),
        "output_tokens": sum(int(item["attributes"].get("gen_ai.usage.output_tokens", 0)) for item in model_spans),
    }


def _cost(record: RunRecord) -> float:
    usage = _usage(record)
    input_rate = float(os.getenv("EVAL_INPUT_COST_PER_1K", "0"))
    output_rate = float(os.getenv("EVAL_OUTPUT_COST_PER_1K", "0"))
    return round(
        usage["input_tokens"] / 1000 * input_rate
        + usage["output_tokens"] / 1000 * output_rate,
        6,
    )


def _duration(record: RunRecord) -> int:
    roots = [item for item in _trace(record) if item["name"].startswith("run ")]
    return int(roots[-1]["duration_ms"]) if roots else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay one persisted agent run")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--prompt-version")
    parser.add_argument("--model-policy", choices=["balanced", "cheap", "stable"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    comparison = asyncio.run(
        replay_run(
            args.run_id,
            prompt_version=args.prompt_version,
            model_policy=args.model_policy,
        )
    )
    rendered = comparison.model_dump_json(indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
