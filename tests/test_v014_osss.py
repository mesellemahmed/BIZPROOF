from __future__ import annotations

from pathlib import Path

from bizproof.v014_osss import (
    certify_v014_osss,
    prepare_osss_source,
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


def test_removes_irrelevant_dynamic_work(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    service,
    x: int,
) -> int:
    service.log(x)
    garbage = service.load_everything()
    result = x + 1
    return result
""",
    )

    preparation = prepare_osss_source(source_file=path)

    assert "load_everything" not in preparation.source

    assert "service.log" not in preparation.source

    result = certify_v014_osss(
        source_file=path,
        evidence_id="dev::slice-simple",
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"
    assert result["v014_osss"]["active"] is True


def test_keeps_control_dependency(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    x: int,
    flag: bool,
) -> int:
    noise = external()
    result = x

    if flag:
        result = result + 1

    return result
""",
    )

    preparation = prepare_osss_source(source_file=path)

    assert "external()" not in preparation.source

    assert "if flag:" in (preparation.source)

    result = certify_v014_osss(
        source_file=path,
        evidence_id="dev::control",
    )

    assert result["certified"] is True


def test_dynamic_control_on_slice_is_not_removed(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    values,
    x: int,
) -> int:
    result = x

    for value in values:
        result = result + value

    return result
""",
    )

    result = certify_v014_osss(
        source_file=path,
        evidence_id="dev::dynamic",
    )

    assert result["certified"] is False

    metadata = result["v014_osss"]

    assert metadata["active"] is False


def test_boundary_on_slice_can_remain_explicit(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    user,
    x: int,
) -> bool:
    audit(user)
    return user.active and x > 0
""",
    )

    result = certify_v014_osss(
        source_file=path,
        evidence_id="dev::boundary",
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"


def test_passthrough_boundary_is_not_promoted(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(service) -> bool:
    other = 7
    return service.enabled()
""",
    )

    result = certify_v014_osss(
        source_file=path,
        evidence_id="dev::passthrough",
    )

    assert result["certified"] is False


def test_off_slice_mutation_of_relevant_object_rejected(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    state,
    enabled: bool,
) -> bool:
    state["active"] = enabled
    return state["active"]
""",
    )

    result = certify_v014_osss(
        source_file=path,
        evidence_id="dev::mutation",
    )

    assert result["certified"] is False


def test_deterministic_slice(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    x: int,
) -> int:
    unused = external()
    result = x + 2
    return result
""",
    )

    first = prepare_osss_source(source_file=path)

    second = prepare_osss_source(source_file=path)

    assert first == second


def test_no_case_specific_markers() -> None:
    source = Path("src/bizproof/v014_osss.py").read_text(encoding="utf-8")

    assert "ext-" not in source
    assert "TARGETS" not in source
    assert "ADAPTERS" not in source
