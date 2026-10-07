from __future__ import annotations

from pathlib import Path

from bizproof.v014_obligation_localtypes import (
    certify_obligation_v014_localtypes,
    prepare_localtype_obligation,
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


def test_hvac_enum_like_attributes_are_lifted_from_local_int_context(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    observed_action: int,
    observed_mode: int,
):
    action = observed_action
    if (
        action == HVACAction.OFF
        and observed_mode != HVACMode.OFF
    ):
        action = HVACAction.IDLE
    return action
""",
    )

    result = certify_obligation_v014_localtypes(
        source_file=path,
        case_id="dev::hvac",
    )

    assert result["certified"] is True

    assert result["a_level"] == "A1"

    metadata = result["v014_localtype_boundary"]

    expressions = {item["source_expression"] for item in metadata["bindings"]}

    assert "HVACAction.OFF" in expressions

    assert "HVACMode.OFF" in expressions

    assert "HVACAction.IDLE" in expressions

    assert all(item["type_name"] == "int" for item in metadata["bindings"])


def test_external_attribute_without_type_context_is_not_guessed(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule():
    return http.client.NO_CONTENT
""",
    )

    preparation = prepare_localtype_obligation(source_file=path)

    assert preparation.bindings == ()

    result = certify_obligation_v014_localtypes(
        source_file=path,
        case_id="dev::unknown-attribute",
    )

    assert result["certified"] is False


def test_string_addition_does_not_become_integer_boundary(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(rows):
    return RST_HEADER + rows
""",
    )

    preparation = prepare_localtype_obligation(source_file=path)

    assert preparation.bindings == ()


def test_dictionary_attribute_context_not_guessed(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(manifest):
    data = {
        "id": manifest.id,
    }
    return data
""",
    )

    preparation = prepare_localtype_obligation(source_file=path)

    assert preparation.bindings == ()


def test_local_assignment_propagates_int_type(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int):
    current = x
    current = External.VALUE
    return current
""",
    )

    preparation = prepare_localtype_obligation(source_file=path)

    bindings = {item.source_expression: item.type_name for item in preparation.bindings}

    assert bindings["External.VALUE"] == "int"


def test_compare_peer_propagates_bool_type(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(flag: bool):
    return flag == Feature.ENABLED
""",
    )

    preparation = prepare_localtype_obligation(source_file=path)

    bindings = {item.source_expression: item.type_name for item in preparation.bindings}

    assert bindings["Feature.ENABLED"] == "bool"


def test_preparation_is_deterministic(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int):
    current = x
    if current == External.ZERO:
        current = External.ONE
    return current
""",
    )

    first = prepare_localtype_obligation(source_file=path)

    second = prepare_localtype_obligation(source_file=path)

    assert first == second


def test_no_case_specific_markers() -> None:
    source = Path("src/bizproof/v014_obligation_localtypes.py").read_text(encoding="utf-8")

    assert "ext-" not in source
    assert "TARGETS" not in source
    assert "ADAPTERS" not in source
