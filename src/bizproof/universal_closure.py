from __future__ import annotations

import ast
import copy
import hashlib
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .universal_projection import (
    analyze_universal_projection,
)
from .v014_obligation_localtypes import (
    certify_obligation_v014_localtypes as certify_obligation_v014,
)

JsonDict = dict[str, Any]


class ClosureOutcome(StrEnum):
    CERTIFIED_A1 = "CERTIFIED_A1"
    CERTIFIED_A2 = "CERTIFIED_A2"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class AbstractBinding:
    expression: str
    parameter: str
    type_name: str


@dataclass(frozen=True)
class Obligation:
    obligation_id: str
    source: str


_EFFECT_METHODS = {
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


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical(node: ast.AST) -> str:
    return ast.unparse(node)


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


def _safe_name(expression: str) -> str:
    result = []

    for char in expression:
        if char.isalnum():
            result.append(char)
        else:
            result.append("_")

    return "obs_" + "".join(result).strip("_")


def _annotation_name(
    annotation: ast.expr | None,
) -> str | None:
    if isinstance(
        annotation,
        ast.Name,
    ) and annotation.id in {
        "int",
        "bool",
    }:
        return annotation.id

    return None


def _fixed_tuple_annotation(
    annotation: ast.expr | None,
) -> tuple[str, ...] | None:
    if not isinstance(
        annotation,
        ast.Subscript,
    ):
        return None

    if not (
        isinstance(
            annotation.value,
            ast.Name,
        )
        and annotation.value.id == "tuple"
    ):
        return None

    slice_node = annotation.slice

    if isinstance(
        slice_node,
        ast.Tuple,
    ):
        elements = slice_node.elts
    else:
        elements = [slice_node]

    result: list[str] = []

    for element in elements:
        name = _annotation_name(element)

        if name is None:
            return None

        result.append(name)

    if not result:
        return None

    return tuple(result)


def _parent_map(
    root: ast.AST,
) -> dict[ast.AST, ast.AST]:
    result: dict[
        ast.AST,
        ast.AST,
    ] = {}

    for parent in ast.walk(root):
        for child in ast.iter_child_nodes(parent):
            result[child] = parent

    return result


def _parameter_names(
    function: ast.FunctionDef,
) -> set[str]:
    return {
        argument.arg for argument in (list(function.args.posonlyargs) + list(function.args.args))
    }


def _effect_calls(
    function: ast.FunctionDef,
    parameters: set[str],
) -> tuple[str, ...]:
    result: list[str] = []

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

        if node.func.attr not in _EFFECT_METHODS:
            continue

        root = _root_name(node.func)

        if root not in parameters:
            continue

        expression = _canonical(node)

        if expression not in result:
            result.append(expression)

    return tuple(result)


def _attribute_occurrences(
    function: ast.FunctionDef,
    parameters: set[str],
) -> dict[str, list[ast.Attribute]]:
    parents = _parent_map(function)

    result: dict[
        str,
        list[ast.Attribute],
    ] = {}

    for node in ast.walk(function):
        if not isinstance(
            node,
            ast.Attribute,
        ):
            continue

        root = _root_name(node)

        if root not in parameters:
            continue

        parent = parents.get(node)

        if (
            isinstance(
                parent,
                ast.Attribute,
            )
            and parent.value is node
        ):
            continue

        if (
            isinstance(
                parent,
                ast.Call,
            )
            and parent.func is node
        ):
            continue

        expression = _canonical(node)

        result.setdefault(
            expression,
            [],
        ).append(node)

    return result


def _infer_binding_type(
    function: ast.FunctionDef,
    occurrences: list[ast.Attribute],
) -> str:
    parents = _parent_map(function)

    for node in occurrences:
        parent = parents.get(node)

        if (
            isinstance(
                parent,
                ast.If,
            )
            and parent.test is node
        ):
            return "bool"

        if (
            isinstance(
                parent,
                ast.IfExp,
            )
            and parent.test is node
        ):
            return "bool"

        if isinstance(
            parent,
            ast.BoolOp,
        ):
            return "bool"

        if isinstance(
            parent,
            ast.UnaryOp,
        ) and isinstance(
            parent.op,
            ast.Not,
        ):
            return "bool"

        if isinstance(
            parent,
            ast.Assign,
        ):
            if isinstance(
                parent.value,
                ast.Constant,
            ) and isinstance(
                parent.value.value,
                bool,
            ):
                return "bool"

        if isinstance(
            parent,
            ast.AnnAssign,
        ):
            if isinstance(
                parent.value,
                ast.Constant,
            ) and isinstance(
                parent.value.value,
                bool,
            ):
                return "bool"

        if isinstance(
            parent,
            ast.Return,
        ):
            if (
                isinstance(
                    function.returns,
                    ast.Name,
                )
                and function.returns.id == "bool"
            ):
                return "bool"

    return "int"


def _build_bindings(
    function: ast.FunctionDef,
) -> tuple[
    tuple[AbstractBinding, ...],
    tuple[str, ...],
]:
    parameters = _parameter_names(function)

    occurrences = _attribute_occurrences(
        function,
        parameters,
    )

    bindings: list[AbstractBinding] = []

    state_bindings: list[str] = []

    for expression in sorted(occurrences):
        nodes = occurrences[expression]

        type_name = _infer_binding_type(
            function,
            nodes,
        )

        parameter = _safe_name(expression)

        bindings.append(
            AbstractBinding(
                expression=expression,
                parameter=parameter,
                type_name=type_name,
            )
        )

        if any(
            isinstance(
                node.ctx,
                ast.Store,
            )
            for node in nodes
        ):
            state_bindings.append(parameter)

    return (
        tuple(bindings),
        tuple(state_bindings),
    )


class _ReplaceName(ast.NodeTransformer):
    def __init__(
        self,
        target: str,
        replacement: str,
    ) -> None:
        self.target = target
        self.replacement = replacement

    def visit_Name(
        self,
        node: ast.Name,
    ) -> ast.AST:
        if (
            isinstance(
                node.ctx,
                ast.Load,
            )
            and node.id == self.target
        ):
            return ast.copy_location(
                ast.Name(
                    id=self.replacement,
                    ctx=ast.Load(),
                ),
                node,
            )

        return node


class _NestedLowerer(ast.NodeTransformer):
    def __init__(
        self,
        expansions: dict[
            str,
            tuple[str, ...],
        ],
    ) -> None:
        self.expansions = expansions

    def visit_Call(
        self,
        node: ast.Call,
    ) -> ast.AST:
        node = self.generic_visit(  # type: ignore[assignment]
            node
        )

        if not isinstance(
            node,
            ast.Call,
        ):
            return node

        if not (
            isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            in {
                "all",
                "any",
                "sum",
            }
        ):
            return node

        if len(node.args) != 1:
            return node

        generator = node.args[0]

        if not isinstance(
            generator,
            ast.GeneratorExp,
        ):
            return node

        if len(generator.generators) != 1:
            return node

        comprehension = generator.generators[0]

        if comprehension.ifs:
            return node

        if not isinstance(
            comprehension.target,
            ast.Name,
        ):
            return node

        if not isinstance(
            comprehension.iter,
            ast.Name,
        ):
            return node

        iterable_name = comprehension.iter.id

        if iterable_name not in self.expansions:
            return node

        target_name = comprehension.target.id

        values: list[ast.expr] = []

        for replacement in self.expansions[iterable_name]:
            candidate = copy.deepcopy(generator.elt)

            candidate = _ReplaceName(
                target_name,
                replacement,
            ).visit(candidate)

            if not isinstance(
                candidate,
                ast.expr,
            ):
                return node

            ast.fix_missing_locations(candidate)

            values.append(candidate)

        if not values:
            return node

        if node.func.id == "all":
            return ast.copy_location(
                ast.BoolOp(
                    op=ast.And(),
                    values=values,
                ),
                node,
            )

        if node.func.id == "any":
            return ast.copy_location(
                ast.BoolOp(
                    op=ast.Or(),
                    values=values,
                ),
                node,
            )

        expression = values[0]

        for value in values[1:]:
            expression = ast.BinOp(
                left=expression,
                op=ast.Add(),
                right=value,
            )

        return ast.copy_location(
            expression,
            node,
        )


class _AttributeAndEffectLowerer(ast.NodeTransformer):
    def __init__(
        self,
        mapping: dict[str, str],
        parameters: set[str],
    ) -> None:
        self.mapping = mapping
        self.parameters = parameters

    def visit_Expr(
        self,
        node: ast.Expr,
    ) -> ast.AST | None:
        if isinstance(
            node.value,
            ast.Call,
        ):
            call = node.value

            if isinstance(
                call.func,
                ast.Attribute,
            ):
                root = _root_name(call.func)

                if root in self.parameters and call.func.attr in _EFFECT_METHODS:
                    return None

        return self.generic_visit(node)

    def visit_Attribute(
        self,
        node: ast.Attribute,
    ) -> ast.AST:
        expression = _canonical(node)

        if expression in self.mapping:
            return ast.copy_location(
                ast.Name(
                    id=self.mapping[expression],
                    ctx=copy.deepcopy(node.ctx),
                ),
                node,
            )

        return self.generic_visit(node)


def _expand_fixed_tuples(
    function: ast.FunctionDef,
) -> dict[str, tuple[str, ...]]:
    new_args: list[ast.arg] = []

    expansions: dict[
        str,
        tuple[str, ...],
    ] = {}

    all_args = list(function.args.posonlyargs) + list(function.args.args)

    if function.args.posonlyargs:
        raise ValueError("positional-only arguments unsupported in universal closure")

    for argument in all_args:
        fixed = _fixed_tuple_annotation(argument.annotation)

        if fixed is None:
            new_args.append(argument)
            continue

        names: list[str] = []

        for index, type_name in enumerate(fixed):
            name = f"{argument.arg}_{index}"

            names.append(name)

            new_args.append(
                ast.arg(
                    arg=name,
                    annotation=ast.Name(
                        id=type_name,
                        ctx=ast.Load(),
                    ),
                )
            )

        expansions[argument.arg] = tuple(names)

    function.args.args = new_args

    function.args.posonlyargs = []

    return expansions


def _remove_unused_untyped_arguments(
    function: ast.FunctionDef,
) -> None:
    used = {
        node.id
        for node in ast.walk(function)
        if isinstance(
            node,
            ast.Name,
        )
    }

    retained: list[ast.arg] = []

    for argument in function.args.args:
        type_name = _annotation_name(argument.annotation)

        if type_name is not None:
            retained.append(argument)
            continue

        if argument.arg in used:
            raise ValueError(f"untyped parameter remains semantically active: {argument.arg}")

    function.args.args = retained


def _remaining_calls(
    function: ast.FunctionDef,
) -> tuple[str, ...]:
    result: list[str] = []

    for node in ast.walk(function):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        expression = _canonical(node)

        if expression not in result:
            result.append(expression)

    return tuple(result)


def _shape(
    value: ast.expr,
) -> tuple[str, ...]:
    if isinstance(
        value,
        (
            ast.Tuple,
            ast.List,
        ),
    ):
        return tuple(f"[{index}]" for index in range(len(value.elts)))

    if isinstance(
        value,
        ast.Dict,
    ):
        result: list[str] = []

        for key in value.keys:
            if not isinstance(
                key,
                ast.Constant,
            ):
                raise ValueError("structured dictionary key must be constant")

            result.append("[" + repr(key.value) + "]")

        return tuple(result)

    return ("",)


def _select_component(
    value: ast.expr,
    selector: str,
) -> ast.expr:
    if selector == "":
        return copy.deepcopy(value)

    if isinstance(
        value,
        (
            ast.Tuple,
            ast.List,
        ),
    ):
        index = int(selector[1:-1])

        return copy.deepcopy(value.elts[index])

    if isinstance(
        value,
        ast.Dict,
    ):
        wanted = selector[1:-1]

        for key, item in zip(
            value.keys,
            value.values,
            strict=True,
        ):
            if not isinstance(
                key,
                ast.Constant,
            ):
                continue

            if repr(key.value) == wanted:
                return copy.deepcopy(item)

    raise ValueError("inconsistent structured return shape")


class _ReturnSelector(ast.NodeTransformer):
    def __init__(
        self,
        selector: str,
    ) -> None:
        self.selector = selector

    def visit_Return(
        self,
        node: ast.Return,
    ) -> ast.AST:
        if node.value is None:
            raise ValueError("bare return unsupported")

        return ast.copy_location(
            ast.Return(
                value=_select_component(
                    node.value,
                    self.selector,
                )
            ),
            node,
        )


class _ReturnState(ast.NodeTransformer):
    def __init__(
        self,
        state_name: str,
    ) -> None:
        self.state_name = state_name

    def visit_Return(
        self,
        node: ast.Return,
    ) -> ast.AST:
        return ast.copy_location(
            ast.Return(
                value=ast.Name(
                    id=self.state_name,
                    ctx=ast.Load(),
                )
            ),
            node,
        )


def _function_source(
    function: ast.FunctionDef,
) -> str:
    function.returns = None

    module = ast.Module(
        body=[function],
        type_ignores=[],
    )

    ast.fix_missing_locations(module)

    return ast.unparse(module) + "\n"


def _build_obligations(
    source_file: Path,
) -> tuple[
    tuple[Obligation, ...],
    tuple[AbstractBinding, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
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
        raise ValueError("exactly one top-level function required")

    original = functions[0]

    parameters = _parameter_names(original)

    effects = _effect_calls(
        original,
        parameters,
    )

    (
        bindings,
        state_bindings,
    ) = _build_bindings(original)

    function = copy.deepcopy(original)

    expansions = _expand_fixed_tuples(function)

    function = _NestedLowerer(expansions).visit(function)

    if not isinstance(
        function,
        ast.FunctionDef,
    ):
        raise ValueError("nested lowering failed")

    mapping = {binding.expression: binding.parameter for binding in bindings}

    function = _AttributeAndEffectLowerer(
        mapping,
        parameters,
    ).visit(function)

    if not isinstance(
        function,
        ast.FunctionDef,
    ):
        raise ValueError("attribute lowering failed")

    existing_names = {argument.arg for argument in function.args.args}

    for binding in bindings:
        if binding.parameter in existing_names:
            continue

        function.args.args.append(
            ast.arg(
                arg=binding.parameter,
                annotation=ast.Name(
                    id=binding.type_name,
                    ctx=ast.Load(),
                ),
            )
        )

        existing_names.add(binding.parameter)

    _remove_unused_untyped_arguments(function)

    remaining_calls = _remaining_calls(function)

    if remaining_calls:
        raise ValueError("unabstracted calls remain: " + ", ".join(remaining_calls))

    returns = [
        node
        for node in ast.walk(function)
        if isinstance(
            node,
            ast.Return,
        )
    ]

    obligations: list[Obligation] = []

    if returns:
        if any(node.value is None for node in returns):
            raise ValueError("bare return unsupported")

        first_value = returns[0].value

        assert first_value is not None

        shape = _shape(first_value)

        for node in returns[1:]:
            assert node.value is not None

            if _shape(node.value) != shape:
                raise ValueError("inconsistent return shapes")

        for selector in shape:
            projected = copy.deepcopy(function)

            projected = _ReturnSelector(selector).visit(projected)

            assert isinstance(
                projected,
                ast.FunctionDef,
            )

            obligations.append(
                Obligation(
                    obligation_id=("return" + selector),
                    source=_function_source(projected),
                )
            )

    for state_name in state_bindings:
        projected = copy.deepcopy(function)

        projected = _ReturnState(state_name).visit(projected)

        assert isinstance(
            projected,
            ast.FunctionDef,
        )

        obligations.append(
            Obligation(
                obligation_id=("state::" + state_name),
                source=_function_source(projected),
            )
        )

    deduped: list[Obligation] = []

    seen: set[str] = set()

    for obligation in obligations:
        digest = _sha256_text(obligation.source)

        if digest in seen:
            continue

        seen.add(digest)

        deduped.append(obligation)

    return (
        tuple(deduped),
        bindings,
        effects,
        state_bindings,
    )


def certify_universal(
    *,
    source_file: Path,
    evidence_id: str,
) -> JsonDict:
    projection = analyze_universal_projection(source_file)

    if projection.unsupported_nodes:
        return {
            "evidence_id": evidence_id,
            "source_sha256": projection.source_sha256,
            "scientific_outcome": ClosureOutcome.UNSUPPORTED.value,
            "certified": False,
            "a_level": None,
            "reason_code": "unsupported_source_nodes",
            "reason": list(projection.unsupported_nodes),
            "capabilities": [item.value for item in projection.capabilities],
            "case_specific_routing": False,
            "full_arbitrary_source_equivalence": False,
        }

    try:
        (
            obligations,
            bindings,
            effects,
            state_bindings,
        ) = _build_obligations(source_file)

    except (
        ValueError,
        SyntaxError,
    ) as exc:
        return {
            "evidence_id": evidence_id,
            "source_sha256": projection.source_sha256,
            "scientific_outcome": ClosureOutcome.UNSUPPORTED.value,
            "certified": False,
            "a_level": None,
            "reason_code": "closure_lowering_unsupported",
            "reason": str(exc),
            "capabilities": [item.value for item in projection.capabilities],
            "case_specific_routing": False,
            "full_arbitrary_source_equivalence": False,
        }

    if not obligations:
        return {
            "evidence_id": evidence_id,
            "source_sha256": projection.source_sha256,
            "scientific_outcome": ClosureOutcome.UNSUPPORTED.value,
            "certified": False,
            "a_level": None,
            "reason_code": "no_formal_obligations",
            "reason": "projection produced no scalar proof obligations",
            "capabilities": [item.value for item in projection.capabilities],
            "case_specific_routing": False,
            "full_arbitrary_source_equivalence": False,
        }

    proof_results: list[JsonDict] = []

    with tempfile.TemporaryDirectory(prefix="bizproof-v013-universal-closure-") as tmp:
        root = Path(tmp)

        for index, obligation in enumerate(obligations):
            path = root / f"obligation_{index}.py"

            path.write_text(
                obligation.source,
                encoding="utf-8",
            )

            result = certify_obligation_v014(
                source_file=path,
                case_id=(evidence_id + "::" + obligation.obligation_id),
            )

            proof_results.append(
                {
                    "obligation_id": obligation.obligation_id,
                    "source_sha256": _sha256_text(obligation.source),
                    "result": result,
                }
            )

    all_certified = all(
        bool(
            item["result"].get(
                "certified",
                False,
            )
        )
        for item in proof_results
    )

    if not all_certified:
        return {
            "evidence_id": evidence_id,
            "source_sha256": projection.source_sha256,
            "scientific_outcome": ClosureOutcome.UNSUPPORTED.value,
            "certified": False,
            "a_level": None,
            "reason_code": "formal_obligation_failed",
            "formal_obligations": proof_results,
            "bindings": [
                {
                    "expression": item.expression,
                    "parameter": item.parameter,
                    "type_name": item.type_name,
                }
                for item in bindings
            ],
            "effects": list(effects),
            "case_specific_routing": False,
            "full_arbitrary_source_equivalence": False,
        }

    all_a2 = all(item["result"].get("a_level") == "A2" for item in proof_results)

    if effects:
        outcome = ClosureOutcome.CERTIFIED_A1

        level = "A1"

    elif all_a2:
        outcome = ClosureOutcome.CERTIFIED_A2

        level = "A2"

    else:
        outcome = ClosureOutcome.CERTIFIED_A1

        level = "A1"

    capabilities = [item.value for item in projection.capabilities]

    return {
        "evidence_id": evidence_id,
        "source_sha256": projection.source_sha256,
        "scientific_outcome": outcome.value,
        "certified": True,
        "a_level": level,
        "capabilities": capabilities,
        "formal_obligations": proof_results,
        "formal_obligation_count": len(proof_results),
        "a2_obligation_count": sum(
            1 for item in proof_results if item["result"].get("a_level") == "A2"
        ),
        "bindings": [
            {
                "expression": item.expression,
                "parameter": item.parameter,
                "type_name": item.type_name,
            }
            for item in bindings
        ],
        "state_bindings": list(state_bindings),
        "effects": list(effects),
        "effect_semantics_formally_proved": False if effects else None,
        "case_specific_routing": False,
        "historical_target_tables_used": False,
        "human_authored_case_adapters_used": False,
        "external_holdout_used": False,
        "full_arbitrary_source_equivalence": False,
        "claim_scope": (
            "formal equivalence evidence for scalarized "
            "observational projections under explicit "
            "parameter/binding abstraction; external effect "
            "occurrence is structurally recorded but external "
            "effect semantics are not inferred"
        ),
    }
