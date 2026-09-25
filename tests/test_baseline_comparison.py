from pathlib import Path

from bizproof.baseline_comparison import run_baseline_comparison

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "benchmarks" / "v0.3" / "catalog.json"


def test_small_baseline_comparison(tmp_path: Path) -> None:
    summary = run_baseline_comparison(
        CATALOG,
        tmp_path / "summary.json",
        tmp_path / "details.csv",
        max_rules=1,
        mutants_per_rule=1,
        hypothesis_examples=50,
        crosshair_condition_timeout=0.25,
        crosshair_process_timeout=5.0,
    )

    assert summary["passed"] is True
    assert summary["rules_checked"] == 1
    assert summary["cases_checked"] == 2
    assert summary["methods"]["bizproof"]["mutants_detected"] == 1
    assert summary["methods"]["bizproof"]["correct_false_alarms"] == 0
    assert summary["tool_errors"] == []

    bizproof = summary["methods"]["bizproof"]
    hypothesis = summary["methods"]["hypothesis"]
    crosshair = summary["methods"]["crosshair"]

    assert "classification_accuracy" not in bizproof
    assert "classification_accuracy" not in hypothesis
    assert "classification_accuracy" not in crosshair

    assert bizproof["proof_capable"] is True
    assert bizproof["correct_cases_proved"] == 1
    assert bizproof["correct_cases_inconclusive"] == 0
    assert bizproof["proof_rate_on_correct"] == 1.0

    assert hypothesis["proof_capable"] is False
    assert hypothesis["correct_cases_proved"] == 0
    assert hypothesis["correct_cases_inconclusive"] == 1
    assert hypothesis["proof_rate_on_correct"] == 0.0

    assert crosshair["proof_capable"] is False
    assert crosshair["correct_cases_proved"] == 0
    assert crosshair["correct_cases_inconclusive"] == 1
    assert crosshair["proof_rate_on_correct"] == 0.0
