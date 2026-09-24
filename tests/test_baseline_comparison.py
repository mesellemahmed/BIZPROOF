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
