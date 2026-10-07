from __future__ import annotations

from pathlib import Path

import pytest

from bizproof.universal_certifier import (
    Capability,
    Resolution,
    analyze_source,
    certify_source,
    is_forbidden_external_holdout,
)


def _write(
    tmp_path: Path,
    source: str,
) -> Path:
    path = tmp_path / "candidate.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    return path


def test_scalar_add_is_supported(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("def total(a: int, b: int) -> int:\n    return a + b\n"),
    )

    analysis = analyze_source(path)

    assert analysis.resolution is Resolution.SUPPORTED

    assert analysis.capability is Capability.PURE_SCALAR

    assert analysis.projection == ("a + b")


def test_scalar_add_reaches_a2(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("def total(a: int, b: int) -> int:\n    return a + b\n"),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-add",
    )

    assert result["scientific_outcome"] == "CERTIFIED_A2"

    assert result["certified"] is True

    assert result["a_level"] == "A2"

    assert result["mutant_refuted"] is True


def test_comparison_reaches_a2(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("def eligible(age: int, minimum: int) -> bool:\n    return age >= minimum\n"),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-threshold",
    )

    assert result["scientific_outcome"] == "CERTIFIED_A2"


def test_boolean_rule_reaches_a2(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("def allowed(active: bool, blocked: bool) -> bool:\n    return active and not blocked\n"),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-bool",
    )

    assert result["scientific_outcome"] == "CERTIFIED_A2"


def test_if_expression_reaches_a2(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("def adjust(value: int) -> int:\n    return value + 1 if value > 0 else value - 1\n"),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-ifexp",
    )

    assert result["scientific_outcome"] == "CERTIFIED_A2"

    assert result["capability"] == "CONTROL_FLOW_SCALAR"

    assert result["formal"]["verdict"] == "PROVED"

    assert result["mutant"]["verdict"] == "DISPROVED"

    assert result["mutant"]["replay_validated"] is True


def test_external_call_is_unsupported(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("def normalized(value: int) -> int:\n    return abs(value)\n"),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-call",
    )

    assert result["scientific_outcome"] == "UNSUPPORTED"

    assert result["reason_code"] == "unsupported_expression"


def test_two_functions_are_ambiguous(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        (
            "def one(x: int) -> int:\n"
            "    return x + 1\n"
            "\n"
            "def two(x: int) -> int:\n"
            "    return x + 2\n"
        ),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-ambiguous",
    )

    assert result["scientific_outcome"] == "AMBIGUOUS"


def test_indented_function_is_dedented(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("    def score(x: int) -> int:\n        return x * 2\n"),
    )

    analysis = analyze_source(path)

    assert analysis.dedented is True

    assert analysis.resolution is Resolution.SUPPORTED


def test_holdout_path_is_forbidden() -> None:
    path = Path("benchmarks/v0.12/external_validation/cohort_freeze/cases/ext-deadbeef.py")

    assert is_forbidden_external_holdout(path) is True


def test_holdout_access_raises() -> None:
    path = Path("benchmarks/v0.12/external_validation/cohort_freeze/cases/ext-deadbeef.py")

    with pytest.raises(
        ValueError,
        match="holdout",
    ):
        analyze_source(path)


def test_unbounded_python_int_domain_is_supported(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("def identity(value: int) -> int:\n    return value\n"),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-unbounded-int",
    )

    assert result["certified"] is True

    assert result["formal"]["verdict"] == "PROVED"


def test_large_integer_not_artificially_bounded(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("def shift(value: int) -> int:\n    return value + 1000000000000000000000000000000\n"),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-large-int",
    )

    assert result["certified"] is True

    assert result["formal"]["verdict"] == "PROVED"


def test_local_assignment_reaches_a2(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("def compute(x: int) -> int:\n    y = x + 1\n    return y * 2\n"),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-assign",
    )

    assert result["scientific_outcome"] == "CERTIFIED_A2"

    assert result["capability"] == "CONTROL_FLOW_SCALAR"


def test_if_return_reaches_a2(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("def adjust(x: int) -> int:\n    if x > 0:\n        return x + 1\n    return x - 1\n"),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-if-return",
    )

    assert result["scientific_outcome"] == "CERTIFIED_A2"


def test_assignment_if_return_reaches_a2(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        (
            "def adjust(x: int) -> int:\n"
            "    y = x + 1\n"
            "    if y > 0:\n"
            "        return y * 2\n"
            "    return y - 2\n"
        ),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-assign-if-return",
    )

    assert result["scientific_outcome"] == "CERTIFIED_A2"


def test_branch_assignment_merge_reaches_a2(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        (
            "def adjust(x: int) -> int:\n"
            "    y = x + 1\n"
            "    if y > 0:\n"
            "        y = y * 2\n"
            "    else:\n"
            "        y = y - 2\n"
            "    return y\n"
        ),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-branch-merge",
    )

    assert result["scientific_outcome"] == "CERTIFIED_A2"


def test_annotated_assignment_reaches_a2(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("def adjust(x: int) -> int:\n    y: int = x + 3\n    return y * 2\n"),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-annassign",
    )

    assert result["scientific_outcome"] == "CERTIFIED_A2"


def test_loop_stays_unsupported(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        ("def adjust(x: int) -> int:\n    while x > 0:\n        x = x - 1\n    return x\n"),
    )

    result = certify_source(
        source_file=path,
        case_id="synthetic-loop",
    )

    assert result["scientific_outcome"] == "UNSUPPORTED"

    assert result["reason_code"] == "unsupported_control_flow"

    assert result["reason"] == "unsupported_statement:While"
