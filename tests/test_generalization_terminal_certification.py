from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_terminal_certification")


def test_assistance_level_a0() -> None:

    module = _module()

    assert (
        module._classify_certified_level(
            explicit_scalar_adapter=False,
            declarative_bindings=False,
        )
        == "CERTIFIED_A0"
    )


def test_assistance_level_a1() -> None:

    module = _module()

    assert (
        module._classify_certified_level(
            explicit_scalar_adapter=False,
            declarative_bindings=True,
        )
        == "CERTIFIED_A1"
    )


def test_assistance_level_a2_precedence() -> None:

    module = _module()

    assert (
        module._classify_certified_level(
            explicit_scalar_adapter=True,
            declarative_bindings=True,
        )
        == "CERTIFIED_A2"
    )


def test_protocol_level_parser(
    tmp_path: Path,
) -> None:

    module = _module()

    path = tmp_path / "protocol.md"

    path.write_text(
        "- `CERTIFIED_A0`: certified without human "
        "semantic mapping or adapter rewriting.\n"
        "- `CERTIFIED_A1`: certified with declarative "
        "source-to-BVC bindings only.\n"
        "- `CERTIFIED_A2`: certified with an explicit "
        "human-authored scalar semantic adapter.\n",
        encoding="utf-8",
    )

    result = module._protocol_levels(path)

    assert set(result) == {
        "CERTIFIED_A0",
        "CERTIFIED_A1",
        "CERTIFIED_A2",
    }


def test_canonical_digest_is_stable() -> None:

    module = _module()

    first = {
        "a": 1,
        "b": 2,
    }

    second = {
        "b": 2,
        "a": 1,
    }

    assert module._canonical_digest(first) == module._canonical_digest(second)
