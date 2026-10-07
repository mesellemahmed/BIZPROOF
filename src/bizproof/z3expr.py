from __future__ import annotations

import ast
from collections.abc import Mapping

import z3

from .expressions import ExpressionError, parse_expression


class Z3ExpressionCompiler:
    def __init__(self, symbols: Mapping[str, z3.ExprRef]) -> None:
        self._symbols = dict(symbols)

    def compile_text(self, expression: str) -> z3.ExprRef:
        tree = parse_expression(expression)
        return self.compile_node(tree.body)

    def compile_boolean_text(self, expression: str) -> z3.BoolRef:
        compiled = self.compile_text(expression)
        return self.require_bool(compiled, "business expression")

    @staticmethod
    def require_bool(expression: z3.ExprRef, context: str) -> z3.BoolRef:
        if not z3.is_bool(expression):
            raise ExpressionError(f"{context} must be boolean")
        return expression

    @staticmethod
    def _require_arithmetic(expression: z3.ExprRef, context: str) -> z3.ArithRef:
        if not z3.is_arith(expression):
            raise ExpressionError(f"{context} must be arithmetic")
        return expression

    def compile_node(
        self,
        node: ast.AST,
        env: Mapping[str, z3.ExprRef] | None = None,
    ) -> z3.ExprRef:
        symbols = self._symbols if env is None else env

        try:
            if isinstance(node, ast.Constant):
                if isinstance(node.value, bool):
                    return z3.BoolVal(node.value)
                if isinstance(node.value, int):
                    return z3.IntVal(node.value)
                raise ExpressionError(f"unsupported constant type: {type(node.value).__name__}")

            if isinstance(node, ast.Name):
                try:
                    return symbols[node.id]
                except KeyError as exc:
                    raise ExpressionError(f"unknown symbol: {node.id}") from exc

            if isinstance(node, ast.BoolOp):
                parts = [
                    self.require_bool(
                        self.compile_node(value, symbols),
                        "boolean operand",
                    )
                    for value in node.values
                ]
                if isinstance(node.op, ast.And):
                    return z3.And(*parts)
                if isinstance(node.op, ast.Or):
                    return z3.Or(*parts)
                raise ExpressionError(f"unsupported bool op: {type(node.op).__name__}")

            if isinstance(node, ast.UnaryOp):
                operand = self.compile_node(node.operand, symbols)
                if isinstance(node.op, ast.Not):
                    return z3.Not(self.require_bool(operand, "not operand"))
                if isinstance(node.op, ast.USub):
                    return -self._require_arithmetic(operand, "unary minus operand")
                if isinstance(node.op, ast.UAdd):
                    return self._require_arithmetic(operand, "unary plus operand")
                raise ExpressionError(f"unsupported unary op: {type(node.op).__name__}")

            if isinstance(node, ast.BinOp):
                left = self._require_arithmetic(
                    self.compile_node(node.left, symbols),
                    "left arithmetic operand",
                )
                right = self._require_arithmetic(
                    self.compile_node(node.right, symbols),
                    "right arithmetic operand",
                )

                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                raise ExpressionError(
                    f"unsupported binary op: {type(node.op).__name__}; "
                    "division and modulo are intentionally disabled"
                )

            if isinstance(node, ast.Compare):
                left = self.compile_node(node.left, symbols)
                clauses: list[z3.BoolRef] = []

                for operator, comparator in zip(node.ops, node.comparators, strict=True):
                    right = self.compile_node(comparator, symbols)

                    if isinstance(operator, ast.Eq):
                        clause = left == right
                    elif isinstance(operator, ast.NotEq):
                        clause = left != right
                    elif isinstance(operator, ast.Lt):
                        clause = left < right
                    elif isinstance(operator, ast.LtE):
                        clause = left <= right
                    elif isinstance(operator, ast.Gt):
                        clause = left > right
                    elif isinstance(operator, ast.GtE):
                        clause = left >= right
                    else:
                        raise ExpressionError(f"unsupported comparison: {type(operator).__name__}")

                    if not z3.is_bool(clause):
                        raise ExpressionError("comparison did not produce a boolean expression")
                    clauses.append(clause)
                    left = right

                return z3.And(*clauses)

            if isinstance(node, ast.IfExp):
                condition = self.require_bool(
                    self.compile_node(node.test, symbols),
                    "conditional expression predicate",
                )
                then_value = self.compile_node(node.body, symbols)
                else_value = self.compile_node(node.orelse, symbols)
                if then_value.sort() != else_value.sort():
                    raise ExpressionError(
                        "conditional expression branches must have the same symbolic type"
                    )
                return z3.If(condition, then_value, else_value)

        except z3.Z3Exception as exc:
            raise ExpressionError(f"z3 expression error: {exc}") from exc

        raise ExpressionError(f"unsupported AST node: {type(node).__name__}")
