from __future__ import annotations

import ast
import importlib
from typing import Any


def _module() -> Any:
    return importlib.import_module("bizproof.generalization_symbolic_probe")


def _function(source: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_direct_return_ir() -> None:
    module = _module()
    builder = module.IRBuilder()

    result = builder.function(
        _function("def rule(x, y):\n    total = x + y\n    return total > 0\n")
    )

    assert result["ir_version"] == "BSIR-SKELETON-0.11"
    assert result["return"]["op"] == "compare"
    assert builder.bindings == {}


def test_call_becomes_explicit_binding() -> None:
    module = _module()
    builder = module.IRBuilder()

    result = builder.function(
        _function(
            "def rule(entity, period):\n"
            "    amount = entity('amount', period)\n"
            "    return amount > 0\n"
        )
    )

    assert result["return"]["op"] == "compare"
    assert len(builder.bindings) == 1

    binding = next(iter(builder.bindings.values()))
    assert binding["kind"] == "CALL"
    assert binding["primitive"] == "entity"


def test_attribute_becomes_explicit_binding() -> None:
    module = _module()
    builder = module.IRBuilder()

    result = builder.function(_function("def rule(order):\n    return order.total > 0\n"))

    assert result["return"]["op"] == "compare"
    assert len(builder.bindings) == 1

    binding = next(iter(builder.bindings.values()))
    assert binding["kind"] == "ATTRIBUTE"
    assert binding["primitive"] == "total"


def test_local_assignment_is_substituted() -> None:
    module = _module()
    builder = module.IRBuilder()

    result = builder.function(
        _function("def rule(x):\n    a = x + 1\n    b = a * 2\n    return b\n")
    )

    assert result["return"]["op"] == "mul"


def test_statement_if_routes_to_review() -> None:
    module = _module()
    builder = module.IRBuilder()

    function = _function("def rule(x):\n    if x > 0:\n        return 1\n    return 0\n")

    try:
        builder.function(function)
    except module.UnsupportedStructure as exc:
        assert "statement-level If" in str(exc)
    else:
        raise AssertionError("expected UnsupportedStructure")


def test_subscript_routes_to_review() -> None:
    module = _module()
    builder = module.IRBuilder()

    function = _function("def rule(items):\n    return items[0]\n")

    try:
        builder.function(function)
    except module.UnsupportedStructure as exc:
        assert "Subscript" in str(exc)
    else:
        raise AssertionError("expected UnsupportedStructure")


def test_pass_is_explicit_none_return() -> None:
    module = _module()
    builder = module.IRBuilder()

    result = builder.function(_function("def rule():\n    pass\n"))

    assert result["return"] == {
        "op": "const",
        "type": "none",
        "value": None,
    }
