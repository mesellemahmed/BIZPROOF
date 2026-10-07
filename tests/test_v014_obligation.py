from __future__ import annotations

from pathlib import Path

from bizproof.v014_obligation import (
    certify_obligation_v014,
    prepare_obligation_source,
)


def _write(
    tmp_path: Path,
    source: str,
) -> Path:
    path = tmp_path / "candidate.py"

    path.write_text(
        source.strip() + "\n",
        encoding="utf-8",
    )

    return path


def test_zero_argument_obligation(
    tmp_path: Path,
) -> None:
    source = _write(
        tmp_path,
        """
def rule() -> int:
    return 7
""",
    )

    result = certify_obligation_v014(
        source_file=source,
        case_id="dev::zero-arg",
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"

    metadata = result["v014_obligation_boundary"]

    assert metadata["unit_parameter_added"] is True


def test_attribute_obligation(
    tmp_path: Path,
) -> None:
    source = _write(
        tmp_path,
        """
def rule(
    context,
    x: int,
) -> int:
    return context.offset + x
""",
    )

    result = certify_obligation_v014(
        source_file=source,
        case_id="dev::attribute",
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"

    metadata = result["v014_obligation_boundary"]

    kinds = {binding["kind"] for binding in metadata["bindings"]}

    assert "FORMAL_OPAQUE_ATTRIBUTE" in kinds

    assert "context" in metadata["removed_inactive_parameters"]


def test_external_integer_constant(
    tmp_path: Path,
) -> None:
    source = _write(
        tmp_path,
        """
def rule(x: int) -> bool:
    return x > LIMIT
""",
    )

    result = certify_obligation_v014(
        source_file=source,
        case_id="dev::global-int",
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"

    metadata = result["v014_obligation_boundary"]

    assert any(binding["source_expression"] == "LIMIT" for binding in metadata["bindings"])


def test_external_boolean_constant(
    tmp_path: Path,
) -> None:
    source = _write(
        tmp_path,
        """
def rule(x: bool) -> bool:
    return x and FEATURE_ENABLED
""",
    )

    result = certify_obligation_v014(
        source_file=source,
        case_id="dev::global-bool",
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"


def test_string_semantics_remain_unsupported(
    tmp_path: Path,
) -> None:
    source = _write(
        tmp_path,
        """
def rule(x: int):
    return "prefix"
""",
    )

    result = certify_obligation_v014(
        source_file=source,
        case_id="dev::string",
    )

    assert result["certified"] is False


def test_assert_semantics_remain_unsupported(
    tmp_path: Path,
) -> None:
    source = _write(
        tmp_path,
        """
def rule(x: int) -> int:
    assert x > 0
    return x + 1
""",
    )

    result = certify_obligation_v014(
        source_file=source,
        case_id="dev::assert",
    )

    assert result["certified"] is False


def test_missing_return_semantics_remain_unsupported(
    tmp_path: Path,
) -> None:
    source = _write(
        tmp_path,
        """
def rule(x: int) -> int:
    if x > 0:
        return x
""",
    )

    result = certify_obligation_v014(
        source_file=source,
        case_id="dev::missing-return",
    )

    assert result["certified"] is False


def test_preparation_deterministic(
    tmp_path: Path,
) -> None:
    source = _write(
        tmp_path,
        """
def rule(
    obj,
    x: int,
) -> int:
    return obj.delta + x
""",
    )

    first = prepare_obligation_source(source_file=source)

    second = prepare_obligation_source(source_file=source)

    assert first == second


def test_no_case_specific_ids() -> None:
    source = Path("src/bizproof/v014_obligation.py").read_text(encoding="utf-8")

    assert "ext-" not in source
    assert "TARGETS" not in source
    assert "ADAPTERS" not in source
