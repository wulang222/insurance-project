"""Day 7-compatible entrypoint for running the complete evaluation suite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.run import run_evals


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the insurance Agent eval suite")
    parser.add_argument("--suite", choices=["all"], default="all")
    parser.add_argument(
        "--datasets",
        type=Path,
        default=Path(__file__).with_name("datasets"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("reports") / "day7-final.json",
    )
    args = parser.parse_args()
    report = run_evals(args.datasets)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "suite": args.suite,
                "total_cases": report["total_cases"],
                "passed_cases": report["passed_cases"],
                "all_targets_met": report["all_targets_met"],
                "report": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    if not report["all_targets_met"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
