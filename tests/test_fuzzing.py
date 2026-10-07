from pathlib import Path

from bizproof.fuzzing import generate_corpus, run_fuzz_differential


def test_generated_corpus_is_deterministic(tmp_path: Path) -> None:
    first = generate_corpus(tmp_path / "first", cases=12, seed=42)
    second = generate_corpus(tmp_path / "second", cases=12, seed=42)

    assert [case.template for case in first] == [case.template for case in second]
    assert [case.variant for case in first] == [case.variant for case in second]
    assert [case.expected_verdict for case in first] == [case.expected_verdict for case in second]


def test_small_fuzz_differential_suite_passes(tmp_path: Path) -> None:
    summary = run_fuzz_differential(
        tmp_path / "generated",
        cases=24,
        seed=20260923,
    )

    assert summary.cases_checked == 24
    assert summary.oracle_label_mismatches == 0
    assert summary.verdict_disagreements == 0
    assert summary.false_proved == 0
    assert summary.false_disproved == 0
    assert summary.enum_unknowns == 0
    assert summary.z3_unknowns == 0
    assert summary.invalid_replays == 0
    assert summary.crashes == 0
    assert summary.passed
