from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


class ProjectionCapability(StrEnum):
    SCALAR_VALUE = "SCALAR_VALUE"
    STRUCTURED_VALUE = "STRUCTURED_VALUE"
    OPAQUE_BINDING = "OPAQUE_BINDING"
    NESTED_LOGIC = "NESTED_LOGIC"
    STATE_EFFECT = "STATE_EFFECT"
    UNKNOWN = "UNKNOWN"


class ObservationKind(StrEnum):
    RETURN_COMPONENT = "RETURN_COMPONENT"
    OPAQUE_ATTRIBUTE = "OPAQUE_ATTRIBUTE"
    OPAQUE_CALL = "OPAQUE_CALL"
    NESTED_OPERATOR = "NESTED_OPERATOR"
    STATE_WRITE = "STATE_WRITE"
    EFFECT_CALL = "EFFECT_CALL"


@dataclass(frozen=True)
class ProjectionObservation:
    kind: ObservationKind
    path: str
    expression: str
    symbol: str | None = None


@dataclass(frozen=True)
class UniversalProjection:
    source_sha256: str
    function_name: str
    parameters: tuple[str, ...]
    capabilities: tuple[ProjectionCapability, ...]
    observations: tuple[ProjectionObservation, ...]
    unsupported_nodes: tuple[str, ...]
    case_specific_routing: bool
    claim_scope: str

    def to_json(self) -> JsonDict:
        result = asdict(self)

        result["capabilities"] = [capability.value for capability in self.capabilities]

        result["observations"] = [
            {
                "kind": observation.kind.value,
                "path": observation.path,
                "expression": observation.expression,
                "symbol": observation.symbol,
            }
            for observation in self.observations
        ]

        return result


class ProjectionError(ValueError):
    pass


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical(node: ast.AST) -> str:
    return ast.unparse(node)


def _function_parameters(
    function: ast.FunctionDef,
) -> tuple[str, ...]:
    if function.args.vararg or function.args.kwarg:
        raise ProjectionError("variadic functions are unsupported")

    if function.args.kwonlyargs:
        raise ProjectionError("keyword-only arguments are unsupported")

    return tuple(
        argument.arg for argument in (list(function.args.posonlyargs) + list(function.args.args))
    )


def _root_name(
    node: ast.AST,
) -> str | None:
    current = node

    while isinstance(
        current,
        ast.Attribute,
    ):
        current = current.value

    if isinstance(
        current,
        ast.Name,
    ):
        return current.id

    return None


def _binding_symbol(
    index: int,
) -> str:
    return f"beta_{index}"


def _flatten_return(
    node: ast.expr,
    path: str,
) -> list[ProjectionObservation]:
    if isinstance(
        node,
        ast.Tuple,
    ):
        result: list[ProjectionObservation] = []

        for index, item in enumerate(node.elts):
            result.extend(
                _flatten_return(
                    item,
                    f"{path}[{index}]",
                )
            )

        return result

    if isinstance(
        node,
        ast.List,
    ):
        result = []

        for index, item in enumerate(node.elts):
            result.extend(
                _flatten_return(
                    item,
                    f"{path}[{index}]",
                )
            )

        return result

    if isinstance(
        node,
        ast.Dict,
    ):
        result = []

        for key, value in zip(
            node.keys,
            node.values,
            strict=True,
        ):
            if key is None:
                raise ProjectionError("dictionary unpacking is unsupported")

            if not isinstance(
                key,
                ast.Constant,
            ):
                raise ProjectionError("structured dictionary keys must be constants")

            key_text = repr(key.value)

            result.extend(
                _flatten_return(
                    value,
                    f"{path}[{key_text}]",
                )
            )

        return result

    return [
        ProjectionObservation(
            kind=ObservationKind.RETURN_COMPONENT,
            path=path,
            expression=_canonical(node),
        )
    ]


def _return_observations(
    function: ast.FunctionDef,
) -> tuple[
    list[ProjectionObservation],
    bool,
]:
    observations: list[ProjectionObservation] = []

    structured = False

    returns = [
        node
        for node in ast.walk(function)
        if isinstance(
            node,
            ast.Return,
        )
        and node.value is not None
    ]

    for return_index, node in enumerate(returns):
        value = node.value

        if value is None:
            continue

        if isinstance(
            value,
            (
                ast.Tuple,
                ast.List,
                ast.Dict,
            ),
        ):
            structured = True

        root = "return" if len(returns) == 1 else f"return@{return_index}"

        observations.extend(
            _flatten_return(
                value,
                root,
            )
        )

    return (
        observations,
        structured,
    )


def _attribute_bindings(
    function: ast.FunctionDef,
    parameters: set[str],
) -> list[ProjectionObservation]:
    expressions: list[str] = []

    for node in ast.walk(function):
        if not isinstance(
            node,
            ast.Attribute,
        ):
            continue

        if not isinstance(
            node.ctx,
            ast.Load,
        ):
            continue

        root = _root_name(node)

        if root not in parameters:
            continue

        expression = _canonical(node)

        if expression not in expressions:
            expressions.append(expression)

    return [
        ProjectionObservation(
            kind=ObservationKind.OPAQUE_ATTRIBUTE,
            path=expression,
            expression=expression,
            symbol=_binding_symbol(index),
        )
        for index, expression in enumerate(expressions)
    ]


def _nested_logic(
    function: ast.FunctionDef,
) -> list[ProjectionObservation]:
    observations: list[ProjectionObservation] = []

    supported_names = {
        "all",
        "any",
        "sum",
        "min",
        "max",
    }

    for node in ast.walk(function):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Name,
        ):
            continue

        if node.func.id not in supported_names:
            continue

        observations.append(
            ProjectionObservation(
                kind=ObservationKind.NESTED_OPERATOR,
                path=node.func.id,
                expression=_canonical(node),
            )
        )

    for node in ast.walk(function):
        if isinstance(
            node,
            (
                ast.GeneratorExp,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
            ),
        ):
            observations.append(
                ProjectionObservation(
                    kind=ObservationKind.NESTED_OPERATOR,
                    path=type(node).__name__,
                    expression=_canonical(node),
                )
            )

    return observations


def _state_effects(
    function: ast.FunctionDef,
    parameters: set[str],
) -> list[ProjectionObservation]:
    observations: list[ProjectionObservation] = []

    for node in ast.walk(function):
        target: ast.AST | None = None

        if isinstance(
            node,
            ast.Assign,
        ):
            if len(node.targets) == 1:
                target = node.targets[0]

        elif isinstance(
            node,
            ast.AnnAssign,
        ):
            target = node.target

        elif isinstance(
            node,
            ast.AugAssign,
        ):
            target = node.target

        if isinstance(
            target,
            (
                ast.Attribute,
                ast.Subscript,
            ),
        ):
            root = _root_name(target)

            if root in parameters:
                observations.append(
                    ProjectionObservation(
                        kind=ObservationKind.STATE_WRITE,
                        path=_canonical(target),
                        expression=_canonical(node),
                    )
                )

    mutating_methods = {
        "add",
        "append",
        "clear",
        "delete",
        "discard",
        "extend",
        "insert",
        "pop",
        "remove",
        "save",
        "send",
        "set",
        "update",
        "write",
    }

    for node in ast.walk(function):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Attribute,
        ):
            continue

        if node.func.attr not in mutating_methods:
            continue

        root = _root_name(node.func)

        if root not in parameters:
            continue

        observations.append(
            ProjectionObservation(
                kind=ObservationKind.EFFECT_CALL,
                path=_canonical(node.func),
                expression=_canonical(node),
            )
        )

    return observations


def _opaque_calls(
    function: ast.FunctionDef,
    parameters: set[str],
) -> list[ProjectionObservation]:
    observations: list[ProjectionObservation] = []

    for node in ast.walk(function):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if isinstance(
            node.func,
            ast.Name,
        ):
            if node.func.id in {
                "all",
                "any",
                "sum",
                "min",
                "max",
            }:
                continue

            observations.append(
                ProjectionObservation(
                    kind=ObservationKind.OPAQUE_CALL,
                    path=_canonical(node.func),
                    expression=_canonical(node),
                )
            )

            continue

        if isinstance(
            node.func,
            ast.Attribute,
        ):
            root = _root_name(node.func)

            if root not in parameters:
                continue

            if node.func.attr in {
                "add",
                "append",
                "clear",
                "delete",
                "discard",
                "extend",
                "insert",
                "pop",
                "remove",
                "save",
                "send",
                "set",
                "update",
                "write",
            }:
                continue

            observations.append(
                ProjectionObservation(
                    kind=ObservationKind.OPAQUE_CALL,
                    path=_canonical(node.func),
                    expression=_canonical(node),
                )
            )

    return observations


def _unsupported_nodes(
    function: ast.FunctionDef,
) -> tuple[str, ...]:
    names: set[str] = set()

    for node in ast.walk(function):
        if isinstance(
            node,
            (
                ast.AsyncFor,
                ast.AsyncWith,
                ast.Await,
                ast.ClassDef,
                ast.Delete,
                ast.Global,
                ast.Lambda,
                ast.Nonlocal,
                ast.Raise,
                ast.Try,
                ast.While,
                ast.With,
                ast.Yield,
                ast.YieldFrom,
            ),
        ):
            names.add(type(node).__name__)

    return tuple(sorted(names))


def analyze_universal_projection(
    source_file: Path,
) -> UniversalProjection:
    source = source_file.read_text(encoding="utf-8")

    tree = ast.parse(source)

    functions = [
        node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    ]

    if len(functions) != 1:
        raise ProjectionError("source must contain exactly one top-level function")

    function = functions[0]

    parameters = _function_parameters(function)

    parameter_set = set(parameters)

    (
        return_observations,
        structured,
    ) = _return_observations(function)

    binding_observations = _attribute_bindings(
        function,
        parameter_set,
    )

    nested_observations = _nested_logic(function)

    state_observations = _state_effects(
        function,
        parameter_set,
    )

    opaque_call_observations = _opaque_calls(
        function,
        parameter_set,
    )

    capabilities: set[ProjectionCapability] = set()

    if return_observations:
        capabilities.add(
            ProjectionCapability.STRUCTURED_VALUE
            if structured
            else ProjectionCapability.SCALAR_VALUE
        )

    if binding_observations:
        capabilities.add(ProjectionCapability.OPAQUE_BINDING)

    if nested_observations:
        capabilities.add(ProjectionCapability.NESTED_LOGIC)

    if state_observations:
        capabilities.add(ProjectionCapability.STATE_EFFECT)

    unsupported = _unsupported_nodes(function)

    if not capabilities:
        capabilities.add(ProjectionCapability.UNKNOWN)

    observations = (
        return_observations
        + binding_observations
        + nested_observations
        + state_observations
        + opaque_call_observations
    )

    return UniversalProjection(
        source_sha256=_sha256_text(source),
        function_name=function.name,
        parameters=parameters,
        capabilities=tuple(
            sorted(
                capabilities,
                key=lambda item: item.value,
            )
        ),
        observations=tuple(observations),
        unsupported_nodes=unsupported,
        case_specific_routing=False,
        claim_scope=(
            "generic structural semantic projection only; "
            "no business meaning is inferred for opaque "
            "bindings, calls, state, or effects"
        ),
    )


def write_projection(
    source_file: Path,
    output_file: Path,
) -> UniversalProjection:
    projection = analyze_universal_projection(source_file)

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file.write_text(
        json.dumps(
            projection.to_json(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return projection
