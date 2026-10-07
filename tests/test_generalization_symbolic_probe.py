from __future__ import annotations

import ast
import importlib
from typing import Any


def _module() -> Any:
    return importlib.import_module("bizproof.generalization_symbolic_probe")


def _function(source: str) -> ast.FunctionDef:
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_parameter_name_is_input() -> None:
    module = _module()
    builder = module.IRBuilder()

    result = builder.function(_function("def rule(x):\n    return x + 1\n"))

    assert result["return"]["left"] == {
        "op": "input",
        "name": "x",
    }
    assert builder.bindings == {}


def test_free_name_is_global_binding() -> None:
    module = _module()
    builder = module.IRBuilder()

    result = builder.function(_function("def rule(x):\n    return ZERO_DISCOUNT\n"))

    assert result["return"]["op"] == "binding"
    assert len(builder.bindings) == 1

    binding = next(iter(builder.bindings.values()))
    assert binding["kind"] == "GLOBAL_NAME"
    assert binding["primitive"] == "ZERO_DISCOUNT"


def test_pass_shape() -> None:
    module = _module()
    node = _function("def rule():\n    pass\n")
    assert module._semantic_shape(node) == "PASS_STUB"


def test_none_return_shape() -> None:
    module = _module()
    node = _function("def rule():\n    return None\n")
    assert module._semantic_shape(node) == "NONE_RETURN"


def test_substantive_shape() -> None:
    module = _module()
    node = _function("def rule(x):\n    y = x + 1\n    return y\n")
    assert module._semantic_shape(node) == "SUBSTANTIVE_EXPRESSION"


def test_statement_if_still_routes_to_review() -> None:
    module = _module()
    builder = module.IRBuilder()

    try:
        builder.function(_function("def rule(x):\n    if x:\n        return 1\n    return 0\n"))
    except module.UnsupportedStructure:
        pass
    else:
        raise AssertionError("expected UnsupportedStructure")
