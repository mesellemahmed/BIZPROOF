from pathlib import Path

from bizproof.differential import run_differential_suite

ROOT = Path(__file__).resolve().parents[1]


def test_enum_and_z3_agree_on_supported_corpus() -> None:
    summary = run_differential_suite(ROOT / "contracts" / "differential")
    assert summary.contracts_checked >= 3
    assert summary.verdict_disagreements == 0
    assert summary.invalid_replays == 0
    assert summary.unexpected_unknowns == 0
    assert summary.passed
