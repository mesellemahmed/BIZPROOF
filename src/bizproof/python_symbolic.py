from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import z3

from .expressions import ExpressionError
from .z3expr import Z3ExpressionCompiler


class UnsupportedProgram(RuntimeError):
    pass


@dataclass(frozen=True)
class SymbolicPath:
    condition: z3.BoolRef
    result: z3.ExprRef


@dataclass
class _State:
    condition: z3.BoolRef
    env: dict[str, z3.ExprRef]


class PythonSymbolicAnalyzer:
    def __init__(self, source: Path, function_name: str) -> None:
        self._source = source
        self._function_name = function_name

    def extract_paths(
        self,
        symbols: Mapping[str, z3.ExprRef],
    ) -> list[SymbolicPath]:
        try:
            module = ast.parse(self._source.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            raise UnsupportedProgram(f"cannot parse target source: {exc}") from exc

        function = self._find_function(module)
        self._validate_signature(function, symbols)

        if function.decorator_list:
            raise UnsupportedProgram("decorated functions are unsupported")

        states = [_State(condition=z3.BoolVal(True), env=dict(symbols))]
        paths, remaining = self._execute_block(function.body, states)

        if remaining:
            raise UnsupportedProgram("all execution paths must end with return")
        if not paths:
            raise UnsupportedProgram("function has no symbolic return paths")
        return paths

    def _find_function(self, module: ast.Module) -> ast.FunctionDef:
        matches = [
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == self._function_name
        ]
        if len(matches) != 1:
            raise UnsupportedProgram(f"expected exactly one function named {self._function_name!r}")
        return matches[0]

    @staticmethod
    def _validate_signature(
        function: ast.FunctionDef,
        symbols: Mapping[str, z3.ExprRef],
    ) -> None:
        if function.args.posonlyargs:
            raise UnsupportedProgram("positional-only arguments are unsupported")
        if function.args.vararg or function.args.kwarg or function.args.kwonlyargs:
            raise UnsupportedProgram("variadic and keyword-only arguments are unsupported")

        expected_args = [argument.arg for argument in function.args.args]
        if expected_args != list(symbols.keys()):
            raise UnsupportedProgram(
                "function arguments must match contract inputs exactly and in order"
            )

    def _execute_block(
        self,
        statements: list[ast.stmt],
        states: list[_State],
    ) -> tuple[list[SymbolicPath], list[_State]]:
        completed: list[SymbolicPath] = []
        active = states

        for statement in statements:
            next_active: list[_State] = []
            for state in active:
                produced_paths, produced_states = self._execute_statement(statement, state)
                completed.extend(produced_paths)
                next_active.extend(produced_states)
            active = next_active

            if not active:
                break

        return completed, active

    def _execute_statement(
        self,
        statement: ast.stmt,
        state: _State,
    ) -> tuple[list[SymbolicPath], list[_State]]:
        compiler = Z3ExpressionCompiler(state.env)

        if isinstance(statement, ast.Expr):
            if isinstance(statement.value, ast.Constant) and isinstance(
                statement.value.value,
                str,
            ):
                return [], [state]
            raise UnsupportedProgram("expression statements are unsupported")

        if isinstance(statement, ast.Assign):
            if len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
                raise UnsupportedProgram("only simple local assignments are supported")
            name = statement.targets[0].id
            try:
                value = compiler.compile_node(statement.value, state.env)
            except ExpressionError as exc:
                raise UnsupportedProgram(str(exc)) from exc
            new_env = dict(state.env)
            new_env[name] = value
            return [], [_State(condition=state.condition, env=new_env)]

        if isinstance(statement, ast.AnnAssign):
            if not isinstance(statement.target, ast.Name) or statement.value is None:
                raise UnsupportedProgram(
                    "only initialized local annotated assignments are supported"
                )
            name = statement.target.id
            try:
                value = compiler.compile_node(statement.value, state.env)
            except ExpressionError as exc:
                raise UnsupportedProgram(str(exc)) from exc
            new_env = dict(state.env)
            new_env[name] = value
            return [], [_State(condition=state.condition, env=new_env)]

        if isinstance(statement, ast.Return):
            if statement.value is None:
                raise UnsupportedProgram("bare return is unsupported")
            try:
                result = compiler.compile_node(statement.value, state.env)
            except ExpressionError as exc:
                raise UnsupportedProgram(str(exc)) from exc
            return [SymbolicPath(condition=state.condition, result=result)], []

        if isinstance(statement, ast.If):
            try:
                raw_condition = compiler.compile_node(statement.test, state.env)
                condition = compiler.require_bool(raw_condition, "if condition")
            except ExpressionError as exc:
                raise UnsupportedProgram(str(exc)) from exc

            true_state = _State(
                condition=z3.And(state.condition, condition),
                env=dict(state.env),
            )
            false_state = _State(
                condition=z3.And(state.condition, z3.Not(condition)),
                env=dict(state.env),
            )

            true_paths, true_remaining = self._execute_block(statement.body, [true_state])

            if statement.orelse:
                false_paths, false_remaining = self._execute_block(
                    statement.orelse,
                    [false_state],
                )
            else:
                false_paths, false_remaining = [], [false_state]

            return true_paths + false_paths, true_remaining + false_remaining

        raise UnsupportedProgram(f"unsupported statement: {type(statement).__name__}")
