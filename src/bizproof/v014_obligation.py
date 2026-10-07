from __future__ import annotations

import ast
import hashlib
import tempfile
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .universal_certifier import (
    certify_source as certify_source_base,
)

JsonDict = dict[str, Any]


@dataclass(frozen=True)
class ObligationBinding:
    name: str
    kind: str
    source_expression: str
    type_name: str


@dataclass(frozen=True)
class ObligationPreparation:
    source: str
    bindings: tuple[ObligationBinding, ...]
    removed_inactive_parameters: tuple[str, ...]
    unit_parameter_added: bool
    source_sha256: str


def _sha256_text(
    value: str,
) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _annotation_type(
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

    if isinstance(
        annotation,
        ast.Constant,
    ) and annotation.value in {
        "int",
        "bool",
    }:
        return str(annotation.value)

    return None


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


def _argument_types(
    function: ast.FunctionDef,
) -> dict[str, str]:
    result: dict[
        str,
        str,
    ] = {}

    for argument in function.args.args:
        type_name = _annotation_type(argument.annotation)

        if type_name is not None:
            result[argument.arg] = type_name

    return result


def _infer_from_expression(
    node: ast.AST,
    *,
    function: ast.FunctionDef,
    parents: dict[
        ast.AST,
        ast.AST,
    ],
    argument_types: dict[
        str,
        str,
    ],
) -> str | None:
    parent = parents.get(node)

    if parent is None:
        return None

    if isinstance(
        parent,
        ast.BoolOp,
    ):
        return "bool"

    if isinstance(
        parent,
        ast.UnaryOp,
    ):
        if isinstance(
            parent.op,
            ast.Not,
        ):
            return "bool"

        if isinstance(
            parent.op,
            (
                ast.USub,
                ast.UAdd,
            ),
        ):
            return "int"

    if isinstance(
        parent,
        ast.BinOp,
    ):
        other: ast.expr | None = None

        if parent.left is node:
            other = parent.right

        elif parent.right is node:
            other = parent.left

        if isinstance(
            other,
            ast.Constant,
        ):
            if isinstance(
                other.value,
                bool,
            ):
                return "bool"

            if isinstance(
                other.value,
                int,
            ):
                return "int"

            # Strings are intentionally not abstracted here.
            return None

        if isinstance(
            other,
            ast.Name,
        ):
            return argument_types.get(other.id)

        # Arithmetic operators in the current formal backend
        # are integer-valued.
        if isinstance(
            parent.op,
            (
                ast.Add,
                ast.Sub,
                ast.Mult,
            ),
        ):
            return "int"

    if isinstance(
        parent,
        ast.Compare,
    ):
        expressions: list[ast.expr] = [
            parent.left,
            *parent.comparators,
        ]

        for expression in expressions:
            if expression is node:
                continue

            if isinstance(
                expression,
                ast.Constant,
            ):
                if isinstance(
                    expression.value,
                    bool,
                ):
                    return "bool"

                if isinstance(
                    expression.value,
                    int,
                ):
                    return "int"

                return None

            if isinstance(
                expression,
                ast.Name,
            ):
                known = argument_types.get(expression.id)

                if known is not None:
                    return known

    if isinstance(
        parent,
        (
            ast.If,
            ast.IfExp,
            ast.Assert,
        ),
    ):
        if (
            getattr(
                parent,
                "test",
                None,
            )
            is node
        ):
            return "bool"

    if isinstance(
        parent,
        ast.Return,
    ):
        return _annotation_type(function.returns)

    if isinstance(
        parent,
        ast.AnnAssign,
    ):
        return _annotation_type(parent.annotation)

    return None


def _local_names(
    function: ast.FunctionDef,
) -> set[str]:
    names = {argument.arg for argument in function.args.args}

    for node in ast.walk(function):
        if isinstance(
            node,
            ast.Name,
        ) and isinstance(
            node.ctx,
            ast.Store,
        ):
            names.add(node.id)

    return names


class _NearFormalLift(
    ast.NodeTransformer,
):
    def __init__(
        self,
        *,
        function: ast.FunctionDef,
        parents: dict[
            ast.AST,
            ast.AST,
        ],
    ) -> None:
        self._function = function
        self._parents = parents

        self._argument_types = _argument_types(function)

        self._locals = _local_names(function)

        self._counter = 0

        self.bindings: list[ObligationBinding] = []

    def _name(
        self,
    ) -> str:
        self._counter += 1

        return f"__bp_v014_obligation_{self._counter:04d}"

    def _binding(
        self,
        *,
        kind: str,
        source_expression: str,
        type_name: str,
        node: ast.AST,
    ) -> ast.Name:
        name = self._name()

        self.bindings.append(
            ObligationBinding(
                name=name,
                kind=kind,
                source_expression=(source_expression),
                type_name=type_name,
            )
        )

        return ast.copy_location(
            ast.Name(
                id=name,
                ctx=ast.Load(),
            ),
            node,
        )

    def visit_Attribute(
        self,
        node: ast.Attribute,
    ) -> ast.AST:
        if not isinstance(
            node.ctx,
            ast.Load,
        ):
            return self.generic_visit(node)

        parent = self._parents.get(node)

        if (
            isinstance(
                parent,
                ast.Call,
            )
            and parent.func is node
        ):
            return self.generic_visit(node)

        type_name = _infer_from_expression(
            node,
            function=self._function,
            parents=self._parents,
            argument_types=(self._argument_types),
        )

        if type_name is None:
            return self.generic_visit(node)

        return self._binding(
            kind=("FORMAL_OPAQUE_ATTRIBUTE"),
            source_expression=(ast.unparse(node)),
            type_name=type_name,
            node=node,
        )

    def visit_Name(
        self,
        node: ast.Name,
    ) -> ast.AST:
        if not isinstance(
            node.ctx,
            ast.Load,
        ):
            return node

        if node.id in self._locals:
            return node

        if node.id in {
            "True",
            "False",
        }:
            return node

        parent = self._parents.get(node)

        if (
            isinstance(
                parent,
                ast.Call,
            )
            and parent.func is node
        ):
            return node

        type_name = _infer_from_expression(
            node,
            function=self._function,
            parents=self._parents,
            argument_types=(self._argument_types),
        )

        if type_name is None:
            return node

        return self._binding(
            kind=("FORMAL_EXTERNAL_SCALAR"),
            source_expression=node.id,
            type_name=type_name,
            node=node,
        )


def _loaded_names(
    function: ast.FunctionDef,
) -> set[str]:
    return {
        node.id
        for node in ast.walk(function)
        if isinstance(
            node,
            ast.Name,
        )
        and isinstance(
            node.ctx,
            ast.Load,
        )
    }


def prepare_obligation_source(
    *,
    source_file: Path,
) -> ObligationPreparation:
    raw = source_file.read_text(encoding="utf-8")

    source_sha256 = _sha256_text(raw)

    normalized = textwrap.dedent(raw)

    tree = ast.parse(normalized)

    functions = [
        node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    ]

    if len(functions) != 1:
        return ObligationPreparation(
            source=normalized,
            bindings=(),
            removed_inactive_parameters=(),
            unit_parameter_added=False,
            source_sha256=source_sha256,
        )

    function = functions[0]

    parents = _parent_map(function)

    lift = _NearFormalLift(
        function=function,
        parents=parents,
    )

    function.body = [lift.visit(statement) for statement in function.body]

    ast.fix_missing_locations(tree)

    # Boundary variables become explicit typed formal inputs.
    for binding in lift.bindings:
        function.args.args.append(
            ast.arg(
                arg=binding.name,
                annotation=ast.Name(
                    id=binding.type_name,
                    ctx=ast.Load(),
                ),
            )
        )

    # After lifting obj.attr / external constants, object parameters
    # may become completely inactive. Removing ONLY inactive untyped
    # parameters preserves the projected scalar semantics.
    loaded = _loaded_names(function)

    removed: list[str] = []

    kept_arguments: list[ast.arg] = []

    for argument in function.args.args:
        if _annotation_type(argument.annotation) is None and argument.arg not in loaded:
            removed.append(argument.arg)

            continue

        kept_arguments.append(argument)

    function.args.args = kept_arguments

    unit_added = False

    if not function.args.args:
        function.args.args.append(
            ast.arg(
                arg=("__bp_v014_unit"),
                annotation=ast.Name(
                    id="bool",
                    ctx=ast.Load(),
                ),
            )
        )

        unit_added = True

    ast.fix_missing_locations(tree)

    source = ast.unparse(tree) + "\n"

    # Generated source must remain syntactically valid.
    compile(
        source,
        "<v014-obligation>",
        "exec",
    )

    return ObligationPreparation(
        source=source,
        bindings=tuple(lift.bindings),
        removed_inactive_parameters=tuple(removed),
        unit_parameter_added=unit_added,
        source_sha256=source_sha256,
    )


def certify_obligation_v014(
    *,
    source_file: Path,
    case_id: str,
) -> JsonDict:
    preparation = prepare_obligation_source(source_file=source_file)

    abstraction_active = bool(
        preparation.bindings
        or preparation.removed_inactive_parameters
        or preparation.unit_parameter_added
    )

    with tempfile.TemporaryDirectory(prefix="bizproof-v014-obligation-") as tmp_name:
        candidate = Path(tmp_name) / "candidate.py"

        candidate.write_text(
            preparation.source,
            encoding="utf-8",
        )

        result = certify_source_base(
            source_file=candidate,
            case_id=case_id,
        )

    result["v014_obligation_boundary"] = {
        "bindings": [asdict(binding) for binding in preparation.bindings],
        "removed_inactive_parameters": list(preparation.removed_inactive_parameters),
        "unit_parameter_added": preparation.unit_parameter_added,
        "source_sha256": preparation.source_sha256,
        "transformed_sha256": _sha256_text(preparation.source),
        "claim_scope": (
            "formal obligation certified "
            "under explicit scalar boundary "
            "bindings; boundary object/global "
            "semantics are not inferred"
        ),
    }

    if abstraction_active and result.get("certified") is True:
        result["v014_internal_outcome"] = result.get("scientific_outcome")

        result["scientific_outcome"] = "CERTIFIED_A1"

        result["a_level"] = "A1"

        result["mutant_refuted"] = False

        result["reason_code"] = "v014_formal_boundary_a1"

        result["reason"] = "formal obligation proved under explicit V0.14 boundary variables"

    return result
