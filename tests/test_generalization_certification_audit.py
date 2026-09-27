from __future__ import annotations

import ast
import importlib
from typing import Any


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_certification_audit")


def test_call_name() -> None:

    module = _module()

    tree = ast.parse("_sha256_file(path)\n")

    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(
            node,
            ast.Call,
        )
    )

    assert module._call_name(call) == "_sha256_file"


def test_parameter_subscript_detection() -> None:

    module = _module()

    tree = ast.parse("def _reviewer_report(summary, certificates):\n    return certificates['x']\n")

    function = tree.body[0]

    assert isinstance(
        function,
        ast.FunctionDef,
    )

    results = module._direct_parameter_subscripts(function)

    assert len(results) == 1

    assert results[0]["parameter"] == "certificates"


def test_context_contains_target_line() -> None:

    module = _module()

    lines = [
        "a",
        "b",
        "result = _sha256_file(path)",
        "c",
        "d",
    ]

    result = module._context(
        lines,
        3,
        radius=1,
    )

    assert "_sha256_file" in result
