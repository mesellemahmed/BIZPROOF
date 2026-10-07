from __future__ import annotations

import ast
import importlib
from typing import Any


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_a2_authoring")


def _function(
    source: str,
) -> ast.FunctionDef:

    tree = ast.parse(source)

    node = tree.body[0]

    assert isinstance(
        node,
        ast.FunctionDef,
    )

    return node


def test_simple_return() -> None:

    module = _module()

    node = _function(
        """
def rule(x):
    return x + 1
"""
    )

    assert module._shape(node) == "SIMPLE_RETURN_EXPRESSION"


def test_straight_line() -> None:

    module = _module()

    node = _function(
        """
def rule(x):
    y = x + 1
    return y
"""
    )

    assert module._shape(node) == "STRAIGHT_LINE_ASSIGN_RETURN"


def test_branching() -> None:

    module = _module()

    node = _function(
        """
def rule(x):
    if x:
        return 1
    return 0
"""
    )

    assert module._shape(node) == "BRANCHING"


def test_digest_stable() -> None:

    module = _module()

    assert module._canonical_digest(
        {
            "a": 1,
            "b": 2,
        }
    ) == module._canonical_digest(
        {
            "b": 2,
            "a": 1,
        }
    )
