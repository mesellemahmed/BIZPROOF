from __future__ import annotations

from pathlib import Path

from bizproof.v014_osss_hardened import (
    certify_v014_osss_hardened,
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


def test_dead_non_scalar_producer_can_be_removed(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(self) -> bool:
    errors = list(self.channel.values())

    if len(errors) == 0:
        return True

    return any(errors)
""",
    )

    result = certify_v014_osss_hardened(
        source_file=path,
        evidence_id="dev::dead-producer",
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"

    metadata = result["v014_osss_hardened"]

    assert metadata["active"] is True
    assert metadata["removed_dead_producers"]


def test_unknown_equality_operands_use_explicit_tokens(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(context) -> bool:
    obj = get_obj(context)
    return obj.kind != Types.STATIC
""",
    )

    result = certify_v014_osss_hardened(
        source_file=path,
        evidence_id="dev::equality-token",
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"

    metadata = result["v014_osss_hardened"]

    assert len(metadata["equality_tokens"]) == 2

    expressions = {item["source_expression"] for item in metadata["equality_tokens"]}

    assert "obj.kind" in expressions
    assert "Types.STATIC" in expressions


def test_float_annotation_is_not_misclassified_as_int(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(data) -> float:
    if data.enabled():
        return 1
    return external_rate(data)
""",
    )

    result = certify_v014_osss_hardened(
        source_file=path,
        evidence_id="dev::float",
    )

    assert result["certified"] is False

    metadata = result["v014_osss_hardened"]

    assert metadata["active"] is False

    assert "non_scalar_return_annotation" in metadata["reason"]


def test_unknown_unannotated_return_is_rejected(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(service):
    if service.ok:
        return True
    return external_value()
""",
    )

    result = certify_v014_osss_hardened(
        source_file=path,
        evidence_id="dev::unknown-return",
    )

    assert result["certified"] is False


def test_external_passthrough_remains_unsupported(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(user) -> bool:
    adapter = get_adapter()
    return adapter.enabled(user)
""",
    )

    result = certify_v014_osss_hardened(
        source_file=path,
        evidence_id="dev::passthrough",
    )

    assert result["certified"] is False


def test_identity_none_semantics_are_not_opened(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule() -> bool:
    config = current_app.config["STORE"]
    backend = config.get("backend")
    return backend is not None
""",
    )

    result = certify_v014_osss_hardened(
        source_file=path,
        evidence_id="dev::none",
    )

    assert result["certified"] is False


def test_numeric_ordering_unknown_tokens_are_not_created(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(context) -> bool:
    obj = get_obj(context)
    return obj.rank > Levels.MINIMUM
""",
    )

    result = certify_v014_osss_hardened(
        source_file=path,
        evidence_id="dev::ordering",
    )

    assert result["certified"] is False


def test_no_case_specific_markers() -> None:
    source = Path("src/bizproof/v014_osss_hardened.py").read_text(encoding="utf-8")

    assert "ext-" not in source
    assert "TARGETS" not in source
    assert "ADAPTERS" not in source
