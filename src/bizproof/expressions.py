from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any


class ExpressionError(ValueError):
    pass


_ALLOWED_NODE_TYPES = (
    ast.Expression,
    ast.BoolOp,
    ast.UnaryOp,
    ast.BinOp,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.USub,
    ast.UAdd,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)


def parse_expression(expression: str) -> ast.Expression:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"invalid expression: {expression}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODE_TYPES):
            raise ExpressionError(f"unsupported expression node: {type(node).__name__}")
    return tree


def evaluate_expression(expression: str, values: Mapping[str, Any]) -> Any:
    tree = parse_expression(expression)
    code = compile(tree, "<bizproof-expression>", "eval")
    return eval(code, {"__builtins__": {}}, dict(values))


def evaluate_boolean_expression(expression: str, values: Mapping[str, Any]) -> bool:
    value = evaluate_expression(expression, values)
    if type(value) is not bool:
        raise ExpressionError("business preconditions and postconditions must evaluate to bool")
    return value
