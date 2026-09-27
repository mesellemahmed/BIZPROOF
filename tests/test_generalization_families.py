from __future__ import annotations

import importlib
from typing import Any


def _module() -> Any:
    return importlib.import_module("bizproof.generalization_families")


def test_signature_is_order_independent() -> None:
    module = _module()

    assert module._signature(["B", "A", "B"]) == "A+B"


def test_empty_signature_is_none() -> None:
    module = _module()

    assert module._signature([]) == "NONE"


def test_family_id_is_deterministic() -> None:
    module = _module()

    assert module._family_id("BIND", "CALL:max") == module._family_id("BIND", "CALL:max")
