from __future__ import annotations

from pathlib import Path

from evals.run import load_datasets, run_evals
from evals.runner import main as runner_main


DATASETS = Path(__file__).resolve().parents[2] / "evals" / "datasets"


def test_day6_datasets_have_at_least_55_cases() -> None:
    datasets = load_datasets(DATASETS)

    assert len(datasets["routing"]) >= 15
    assert len(datasets["profile_extraction"]) >= 10
    assert len(datasets["tool_selection"]) >= 10
    assert len(datasets["family_plan"]) >= 10
    assert len(datasets["knowledge_grounding"]) + len(datasets["compliance"]) >= 10
    assert sum(map(len, datasets.values())) >= 55


def test_eval_harness_generates_target_report() -> None:
    report = run_evals(DATASETS)

    assert report["total_cases"] >= 55
    assert report["all_targets_met"] is True
    assert report["human_review"]["required"] is True


def test_day7_runner_writes_final_report(tmp_path, monkeypatch, capsys) -> None:
    output = tmp_path / "final.json"
    monkeypatch.setattr(
        "sys.argv",
        ["evals.runner", "--suite", "all", "--output", str(output)],
    )

    runner_main()

    assert output.exists()
    assert '"all_targets_met": true' in capsys.readouterr().out
