from __future__ import annotations

from observability.telemetry import REQUIRED_METRICS, Observability, hash_user_id


def test_trace_keeps_only_allowlisted_non_sensitive_attributes() -> None:
    observability = Observability()
    with observability.span(
        "run test",
        {
            "run.id": "run-1",
            "user.id_hash": hash_user_id("user-1"),
            "phone": "13800138000",
            "password": "secret",
            "health": "高血压",
        },
    ):
        pass

    span = observability.snapshot(run_id="run-1")["spans"][0]
    assert span["attributes"]["user.id_hash"] != "user-1"
    serialized = str(span)
    assert "13800138000" not in serialized
    assert "secret" not in serialized
    assert "高血压" not in serialized


def test_required_metrics_exist_before_first_run() -> None:
    snapshot = Observability().metrics.snapshot()
    available = set(snapshot["counters"]) | set(snapshot["histograms"])

    assert set(REQUIRED_METRICS) <= available
