from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from bizproof.v014_highcoverage import (
    certify_v014_wave4,
    prepare_wave4_source,
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


def _exec_rule(
    source: str,
):
    namespace: dict[str, object] = {}

    exec(
        source,
        namespace,
    )

    return namespace["rule"]


def test_source_attribute_lift_from_known_local_int(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    service,
    x: int,
) -> int:
    value = x
    value = service.offset
    return value + 1
""",
    )

    result = certify_v014_wave4(
        source_file=path,
        evidence_id="dev::source-attribute",
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"

    bindings = result["v014_wave4"]["bindings"]

    assert any(
        item["source_expression"] == "service.offset" and item["type_name"] == "int"
        for item in bindings
    )


def test_source_call_lift_from_known_local_int(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    service,
    x: int,
) -> int:
    value = x
    value = service.fetch()
    return value + 2
""",
    )

    result = certify_v014_wave4(
        source_file=path,
        evidence_id="dev::source-call",
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"

    assert any(
        item["kind"] == "SOURCE_OPAQUE_CALL_RESULT" for item in result["v014_wave4"]["bindings"]
    )


def test_boundary_passthrough_stays_unsupported(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    service,
) -> int:
    return service.fetch()
""",
    )

    result = certify_v014_wave4(
        source_file=path,
        evidence_id="dev::passthrough",
    )

    assert result["certified"] is False


def test_static_range_loop_is_exactly_unrolled(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int) -> int:
    total = x
    for i in range(3):
        total = total + 1
    return total
""",
    )

    preparation = prepare_wave4_source(source_file=path)

    assert preparation.static_loops_unrolled == 1

    assert preparation.static_iterations_unrolled == 3

    original = _exec_rule(path.read_text(encoding="utf-8"))

    transformed = _exec_rule(preparation.source)

    for value in (
        -4,
        0,
        9,
    ):
        assert original(value) == transformed(value)

    result = certify_v014_wave4(
        source_file=path,
        evidence_id="dev::static-range",
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"


def test_static_tuple_for_else_preserved(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int) -> int:
    total = x
    for value in (1, 2):
        total = total + value
    else:
        total = total + 3
    return total
""",
    )

    preparation = prepare_wave4_source(source_file=path)

    original = _exec_rule(path.read_text(encoding="utf-8"))

    transformed = _exec_rule(preparation.source)

    for value in (
        -2,
        0,
        8,
    ):
        assert original(value) == transformed(value)


def test_dynamic_loop_is_not_unrolled(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    values,
    x: int,
) -> int:
    total = x
    for value in values:
        total = total + value
    return total
""",
    )

    preparation = prepare_wave4_source(source_file=path)

    assert preparation.static_loops_unrolled == 0


def test_break_loop_is_not_unrolled(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int) -> int:
    total = x
    for value in (1, 2):
        if value > 1:
            break
        total = total + value
    return total
""",
    )

    preparation = prepare_wave4_source(source_file=path)

    assert preparation.static_loops_unrolled == 0


def test_static_list_comprehension_exact(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int):
    return [x + i for i in (1, 2, 3)]
""",
    )

    preparation = prepare_wave4_source(source_file=path)

    assert preparation.static_list_comprehensions_expanded == 1

    original = _exec_rule(path.read_text(encoding="utf-8"))

    transformed = _exec_rule(preparation.source)

    for value in (
        -3,
        0,
        5,
    ):
        assert original(value) == transformed(value)


def test_boolean_peer_provides_boolean_boundary(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    user,
    enabled: bool,
) -> bool:
    return user.active == enabled
""",
    )

    preparation = prepare_wave4_source(source_file=path)

    bindings = {binding.source_expression: binding.type_name for binding in preparation.bindings}

    assert bindings["user.active"] == "bool"


def test_boundary_runtime_correspondence(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    obj,
    x: int,
) -> int:
    current = x
    current = obj.value
    return current + 4
""",
    )

    preparation = prepare_wave4_source(source_file=path)

    assert len(preparation.bindings) == 1

    binding = preparation.bindings[0]

    original = _exec_rule(path.read_text(encoding="utf-8"))

    transformed = _exec_rule(preparation.source)

    obj = SimpleNamespace(value=11)

    expected = original(
        obj,
        2,
    )

    actual = transformed(
        obj,
        2,
        **{binding.name: obj.value},
    )

    assert expected == actual


def test_no_case_specific_markers() -> None:
    source = Path("src/bizproof/v014_highcoverage.py").read_text(encoding="utf-8")

    assert "ext-" not in source
    assert "TARGETS" not in source
    assert "ADAPTERS" not in source
