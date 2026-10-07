"""Generic controlled helper runtime for V0.12 compositional closure."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, cast


class AttributeTree:
    """Resolve explicitly supplied scalar values by dotted path."""

    def __init__(
        self,
        values: dict[str, Any],
        prefix: str = "",
    ) -> None:
        self._values = values
        self._prefix = prefix

    def __getattr__(
        self,
        name: str,
    ) -> Any:
        path = f"{self._prefix}.{name}" if self._prefix else name

        if path in self._values:
            return self._values[path]

        child_prefix = f"{path}."

        if any(key.startswith(child_prefix) for key in self._values):
            return AttributeTree(
                self._values,
                path,
            )

        raise AttributeError(path)


@dataclass(frozen=True, slots=True)
class ControlledPeriod:
    """Minimal explicit period observation."""

    identity: str

    @property
    def first_month(
        self,
    ) -> ControlledPeriod:
        return self


class ControlledFamily:
    """Explicit family observations used by frozen formulas."""

    def __init__(
        self,
        *,
        scalars: dict[str, Any],
        members: dict[
            str,
            tuple[Any, ...],
        ],
    ) -> None:
        self._scalars = dict(scalars)
        self._members = dict(members)

    def __call__(
        self,
        variable: str,
        period: object,
    ) -> Any:
        del period

        return self._scalars[variable]

    def members(
        self,
        variable: str,
        period: object,
    ) -> tuple[Any, ...]:
        del period

        return self._members[variable]

    def sum(
        self,
        values: tuple[Any, ...],
    ) -> Any:
        return sum(values)

    def any(
        self,
        values: tuple[Any, ...],
        *,
        role: object | None = None,
    ) -> bool:
        del role

        return any(bool(value) for value in values)


class FamilyRole:
    PARENT = "PARENT"


@dataclass(slots=True)
class ControlledHelperEnvironment:
    family_scalars: dict[
        str,
        Any,
    ]

    family_members: dict[
        str,
        tuple[Any, ...],
    ]

    parameter_values: dict[
        str,
        Any,
    ]

    child_counts: dict[
        tuple[int, int],
        int,
    ]

    period_identity: str = "P"

    def family(
        self,
    ) -> ControlledFamily:
        return ControlledFamily(
            scalars=(self.family_scalars),
            members=(self.family_members),
        )

    def period(
        self,
    ) -> ControlledPeriod:
        return ControlledPeriod(self.period_identity)

    def parameters(
        self,
        period: object,
    ) -> AttributeTree:
        del period

        return AttributeTree(self.parameter_values)

    def nb_enf(
        self,
        family: object,
        period: object,
        lower: int | float,
        upper: int | float,
    ) -> int:
        del family
        del period

        key = (
            int(lower),
            int(upper),
        )

        return self.child_counts[key]


def controlled_globals(
    environment: ControlledHelperEnvironment,
) -> dict[str, Any]:
    return {
        "Famille": FamilyRole,
        "max_": max,
        "nb_enf": environment.nb_enf,
        "not_": lambda value: not bool(value),
    }


def compile_frozen_function(
    source: str,
    function_name: str,
    environment: ControlledHelperEnvironment,
) -> Any:
    namespace: dict[
        str,
        Any,
    ] = controlled_globals(environment)

    code = compile(
        source,
        "<frozen-bizproof-source>",
        "exec",
    )

    exec(
        code,
        namespace,
    )

    function = namespace[function_name]

    return function


def execute_frozen_formula(
    source: str,
    function_name: str,
    environment: ControlledHelperEnvironment,
) -> Any:
    function = compile_frozen_function(
        source,
        function_name,
        environment,
    )

    return function(
        environment.family(),
        environment.period(),
        environment.parameters,
    )


class _FinalCompositionMutator(ast.NodeTransformer):
    def __init__(
        self,
        target_name: str,
    ) -> None:
        self.target_name = target_name
        self.mutations = 0

    def visit_Assign(
        self,
        node: ast.Assign,
    ) -> ast.AST:
        node = cast(
            ast.Assign,
            self.generic_visit(node),
        )

        if len(node.targets) != 1:
            return node

        target = node.targets[0]

        if not (
            isinstance(
                target,
                ast.Name,
            )
            and target.id == self.target_name
        ):
            return node

        if not (
            isinstance(
                node.value,
                ast.BinOp,
            )
            and isinstance(
                node.value.op,
                ast.Mult,
            )
        ):
            return node

        node.value.op = ast.Add()

        self.mutations += 1

        return node


def build_final_composition_mutant(
    source: str,
    *,
    target_name: str,
) -> str:
    tree = ast.parse(source)

    mutator = _FinalCompositionMutator(target_name)

    tree = mutator.visit(tree)

    ast.fix_missing_locations(tree)

    if mutator.mutations != 1:
        raise ValueError("expected exactly one target multiplication")

    return ast.unparse(tree)


def execute_final_composition_mutant(
    source: str,
    function_name: str,
    environment: ControlledHelperEnvironment,
    *,
    target_name: str,
) -> Any:
    mutant_source = build_final_composition_mutant(
        source,
        target_name=target_name,
    )

    return execute_frozen_formula(
        mutant_source,
        function_name,
        environment,
    )
