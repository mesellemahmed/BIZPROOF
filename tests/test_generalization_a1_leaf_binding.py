from __future__ import annotations

import ast

from bizproof.generalization_a1_leaf_binding import (
    TARGETS,
    _classify_return,
)


def test_target_count() -> None:

    assert len(TARGETS) == 12


def test_direct_attribute_shape() -> None:

    node = ast.parse(
        """
def f(self):
    return self.name
"""
    ).body[0]

    assert isinstance(
        node,
        ast.FunctionDef,
    )

    result = _classify_return(
        node,
        [
            "self.name",
        ],
    )

    assert result["shape"] == "DIRECT_ATTRIBUTE_RETURN"


def test_equality_conjunction_shape() -> None:

    node = ast.parse(
        """
def f(self, other):
    return (
        self.a == other.a
        and self.b == other.b
    )
"""
    ).body[0]

    assert isinstance(
        node,
        ast.FunctionDef,
    )

    result = _classify_return(
        node,
        [
            "self.a",
            "other.a",
            "self.b",
            "other.b",
        ],
    )

    assert result["shape"] == "BOUND_EQUALITY_CONJUNCTION"

    assert len(result["comparison_pairs"]) == 2


def test_undeclared_attribute_rejected() -> None:

    node = ast.parse(
        """
def f(self):
    return self.other
"""
    ).body[0]

    assert isinstance(
        node,
        ast.FunctionDef,
    )

    result = _classify_return(
        node,
        [
            "self.name",
        ],
    )

    assert result["shape"] == "REVIEW_REQUIRED"
