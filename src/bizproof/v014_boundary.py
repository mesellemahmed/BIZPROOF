from __future__ import annotations

import ast
import hashlib
import tempfile
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from .universal_closure import certify_universal

JsonDict = dict[str, Any]


class BoundaryUnsupported(RuntimeError):
    pass


@dataclass(frozen=True)
class BoundaryBinding:
    name: str
    kind: str
    source_expression: str
    type_name: str


@dataclass(frozen=True)
class BoundaryPreparation:
    normalized_source: str
    bindings: tuple[BoundaryBinding, ...]
    effects: tuple[str, ...]
    signature_abstractions: tuple[str, ...]
    inferred_argument_types: tuple[str, ...]
    unresolved_calls: tuple[str, ...]
    unresolved_subscripts: tuple[str, ...]
    semantic_operator_count: int
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
    ):
        if annotation.id in {
            "int",
            "bool",
        }:
            return annotation.id

    if isinstance(
        annotation,
        ast.Constant,
    ):
        if annotation.value in {
            "int",
            "bool",
        }:
            return str(annotation.value)

    return None


def _parent_map(
    tree: ast.AST,
) -> dict[ast.AST, ast.AST]:
    result: dict[
        ast.AST,
        ast.AST,
    ] = {}

    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            result[child] = parent

    return result


def _root_name(
    node: ast.AST,
) -> str | None:
    current = node

    while isinstance(
        current,
        (
            ast.Attribute,
            ast.Subscript,
        ),
    ):
        current = current.value

    if isinstance(
        current,
        ast.Name,
    ):
        return current.id

    return None


def _loaded_name(
    function: ast.FunctionDef,
    name: str,
) -> bool:
    return any(
        isinstance(
            node,
            ast.Name,
        )
        and isinstance(
            node.ctx,
            ast.Load,
        )
        and node.id == name
        for node in ast.walk(function)
    )


def _simple_context_type(
    node: ast.AST,
    parents: dict[
        ast.AST,
        ast.AST,
    ],
) -> str | None:
    parent = parents.get(node)

    if parent is None:
        return None

    if isinstance(
        parent,
        ast.BinOp,
    ):
        return "int"

    if isinstance(
        parent,
        ast.Compare,
    ):
        other_nodes = [
            parent.left,
            *parent.comparators,
        ]

        others = [item for item in other_nodes if item is not node]

        if any(
            isinstance(
                item,
                ast.Constant,
            )
            and isinstance(
                item.value,
                bool,
            )
            for item in others
        ):
            return "bool"

        return "int"

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
                ast.UAdd,
                ast.USub,
            ),
        ):
            return "int"

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

    if (
        isinstance(
            parent,
            ast.Assert,
        )
        and parent.test is node
    ):
        return "bool"

    if (
        isinstance(
            parent,
            ast.Subscript,
        )
        and parent.slice is node
    ):
        return "int"

    return None


def _infer_name_type(
    function: ast.FunctionDef,
    name: str,
    parents: dict[
        ast.AST,
        ast.AST,
    ],
) -> str | None:
    inferred: set[str] = set()

    for node in ast.walk(function):
        if not (
            isinstance(
                node,
                ast.Name,
            )
            and isinstance(
                node.ctx,
                ast.Load,
            )
            and node.id == name
        ):
            continue

        context = _simple_context_type(
            node,
            parents,
        )

        if context is not None:
            inferred.add(context)

    if len(inferred) == 1:
        return next(iter(inferred))

    return None


def _call_context_type(
    node: ast.Call,
    function: ast.FunctionDef,
    parents: dict[
        ast.AST,
        ast.AST,
    ],
) -> str | None:
    direct = _simple_context_type(
        node,
        parents,
    )

    if direct is not None:
        return direct

    parent = parents.get(node)

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

    if isinstance(
        parent,
        ast.Assign,
    ):
        if len(parent.targets) == 1 and isinstance(
            parent.targets[0],
            ast.Name,
        ):
            return _infer_name_type(
                function,
                parent.targets[0].id,
                parents,
            )

    return None


def _subscript_context_type(
    node: ast.Subscript,
    function: ast.FunctionDef,
    parents: dict[
        ast.AST,
        ast.AST,
    ],
) -> str | None:
    direct = _simple_context_type(
        node,
        parents,
    )

    if direct is not None:
        return direct

    parent = parents.get(node)

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

    if isinstance(
        parent,
        ast.Assign,
    ):
        if len(parent.targets) == 1 and isinstance(
            parent.targets[0],
            ast.Name,
        ):
            return _infer_name_type(
                function,
                parent.targets[0].id,
                parents,
            )

    return None


class _BoundaryLift(
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
        parameter_names: set[str],
    ) -> None:
        self._function = function
        self._parents = parents
        self._parameter_names = parameter_names

        self.bindings: list[BoundaryBinding] = []

        self.effects: list[str] = []

        self.unresolved_calls: list[str] = []

        self.unresolved_subscripts: list[str] = []

        self._counter = 0

    def _binding_name(
        self,
    ) -> str:
        while True:
            self._counter += 1

            candidate = f"__bp_v014_boundary_{self._counter:04d}"

            if candidate not in {argument.arg for argument in self._function.args.args}:
                return candidate

    def _add_binding(
        self,
        *,
        kind: str,
        source_expression: str,
        type_name: str,
    ) -> ast.Name:
        name = self._binding_name()

        self.bindings.append(
            BoundaryBinding(
                name=name,
                kind=kind,
                source_expression=(source_expression),
                type_name=type_name,
            )
        )

        return ast.Name(
            id=name,
            ctx=ast.Load(),
        )

    @staticmethod
    def _preserve_semantic_call(
        node: ast.Call,
    ) -> bool:
        if not isinstance(
            node.func,
            ast.Name,
        ):
            return False

        if node.func.id not in {
            "all",
            "any",
            "sum",
        }:
            return False

        return len(node.args) == 1 and isinstance(
            node.args[0],
            ast.GeneratorExp,
        )

    def visit_Expr(
        self,
        node: ast.Expr,
    ) -> ast.stmt | None:
        if isinstance(
            node.value,
            ast.Constant,
        ) and isinstance(
            node.value.value,
            str,
        ):
            return node

        if isinstance(
            node.value,
            ast.Call,
        ):
            self.effects.append(ast.unparse(node.value))

            marker = ast.Expr(value=ast.Constant(value=("BIZPROOF_EXTERNAL_EFFECT_BOUNDARY")))

            return ast.copy_location(
                marker,
                node,
            )

        transformed = self.generic_visit(node)

        return cast(
            ast.stmt,
            transformed,
        )

    def visit_Call(
        self,
        node: ast.Call,
    ) -> ast.AST:
        if self._preserve_semantic_call(node):
            transformed = self.generic_visit(node)

            return transformed

        type_name = _call_context_type(
            node,
            self._function,
            self._parents,
        )

        source_expression = ast.unparse(node)

        if type_name is None:
            self.unresolved_calls.append(source_expression)

            transformed = self.generic_visit(node)

            return transformed

        self.effects.append("potential-call-effect::" + source_expression)

        return ast.copy_location(
            self._add_binding(
                kind=("OPAQUE_CALL_RESULT"),
                source_expression=(source_expression),
                type_name=type_name,
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
            transformed = self.generic_visit(node)

            return transformed

        parent = self._parents.get(node)

        if (
            isinstance(
                parent,
                ast.Call,
            )
            and parent.func is node
        ):
            transformed = self.generic_visit(node)

            return transformed

        root = _root_name(node)

        if root is None or root not in self._parameter_names:
            transformed = self.generic_visit(node)

            return transformed

        type_name = _simple_context_type(
            node,
            self._parents,
        )

        if type_name is None:
            parent = self._parents.get(node)

            if isinstance(
                parent,
                ast.Return,
            ):
                type_name = _annotation_type(self._function.returns)

            elif isinstance(
                parent,
                ast.AnnAssign,
            ):
                type_name = _annotation_type(parent.annotation)

            elif (
                isinstance(
                    parent,
                    ast.Assign,
                )
                and len(parent.targets) == 1
                and isinstance(
                    parent.targets[0],
                    ast.Name,
                )
            ):
                type_name = _infer_name_type(
                    self._function,
                    parent.targets[0].id,
                    self._parents,
                )

        source_expression = ast.unparse(node)

        if type_name is None:
            transformed = self.generic_visit(node)

            return transformed

        return ast.copy_location(
            self._add_binding(
                kind="OPAQUE_ATTRIBUTE_READ",
                source_expression=(source_expression),
                type_name=type_name,
            ),
            node,
        )

    def visit_Subscript(
        self,
        node: ast.Subscript,
    ) -> ast.AST:
        if not isinstance(
            node.ctx,
            ast.Load,
        ):
            transformed = self.generic_visit(node)

            return transformed

        root = _root_name(node)

        if root is None or root not in self._parameter_names:
            transformed = self.generic_visit(node)

            return transformed

        type_name = _subscript_context_type(
            node,
            self._function,
            self._parents,
        )

        source_expression = ast.unparse(node)

        if type_name is None:
            self.unresolved_subscripts.append(source_expression)

            transformed = self.generic_visit(node)

            return transformed

        return ast.copy_location(
            self._add_binding(
                kind=("OPAQUE_SUBSCRIPT_READ"),
                source_expression=(source_expression),
                type_name=type_name,
            ),
            node,
        )

    def visit_AugAssign(
        self,
        node: ast.AugAssign,
    ) -> ast.AST:
        if not isinstance(
            node.target,
            ast.Name,
        ):
            transformed = self.generic_visit(node)

            return transformed

        target = ast.Name(
            id=node.target.id,
            ctx=ast.Store(),
        )

        left = ast.Name(
            id=node.target.id,
            ctx=ast.Load(),
        )

        value = cast(
            ast.expr,
            self.visit(node.value),
        )

        assignment = ast.Assign(
            targets=[
                target,
            ],
            value=ast.BinOp(
                left=left,
                op=node.op,
                right=value,
            ),
        )

        return ast.copy_location(
            assignment,
            node,
        )


def _semantic_operator_count(
    function: ast.FunctionDef,
    boundary_names: set[str],
) -> int:
    count = 0

    for node in ast.walk(function):
        if isinstance(
            node,
            (
                ast.BinOp,
                ast.BoolOp,
                ast.Compare,
                ast.If,
                ast.IfExp,
                ast.UnaryOp,
            ),
        ):
            count += 1

        elif isinstance(
            node,
            ast.Assign,
        ):
            if isinstance(
                node.value,
                ast.Name,
            ) and (node.value.id in boundary_names):
                continue

            count += 1

        elif isinstance(
            node,
            ast.AnnAssign,
        ):
            if (
                isinstance(
                    node.value,
                    ast.Name,
                )
                and node.value.id in boundary_names
            ):
                continue

            count += 1

    return count


def _unsupported_result(
    *,
    source_file: Path,
    source_sha256: str,
    reason_code: str,
    reason: str,
    metadata: JsonDict | None = None,
) -> JsonDict:
    result: JsonDict = {
        "schema_version": "BIZPROOF-V0.14-BOUNDARY-1",
        "source_file": str(source_file),
        "source_sha256": source_sha256,
        "scientific_outcome": "UNSUPPORTED",
        "certified": False,
        "a_level": None,
        "reason_code": reason_code,
        "reason": reason,
        "formal_obligation_count": 0,
        "a2_obligation_count": 0,
        "capabilities": [],
    }

    if metadata:
        result["v014_boundary"] = metadata

    return result


def prepare_boundary_source(
    *,
    source_file: Path,
) -> BoundaryPreparation:
    raw = source_file.read_text(encoding="utf-8")
    normalized_input = textwrap.dedent(raw)

    source_sha256 = _sha256_text(raw)

    try:
        tree = ast.parse(normalized_input)

    except SyntaxError as exc:
        raise BoundaryUnsupported("parse_error::" + str(exc)) from exc

    async_functions = [
        node
        for node in tree.body
        if isinstance(
            node,
            ast.AsyncFunctionDef,
        )
    ]

    if async_functions:
        raise BoundaryUnsupported("async_semantics_not_modeled")

    functions = [
        node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    ]

    if len(functions) != 1:
        raise BoundaryUnsupported("function_resolution_requires_exactly_one_sync_function")

    function = functions[0]

    if function.decorator_list:
        raise BoundaryUnsupported("decorator_semantics_not_modeled")

    original_parents = _parent_map(function)

    original_parameter_names = {
        argument.arg
        for argument in [
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        ]
    }

    if function.args.vararg is not None:
        original_parameter_names.add(function.args.vararg.arg)

    if function.args.kwarg is not None:
        original_parameter_names.add(function.args.kwarg.arg)

    transformer = _BoundaryLift(
        function=function,
        parents=original_parents,
        parameter_names=(original_parameter_names),
    )

    transformed_node = transformer.visit(tree)

    assert isinstance(
        transformed_node,
        ast.Module,
    )

    ast.fix_missing_locations(transformed_node)

    transformed_functions = [
        node
        for node in transformed_node.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    ]

    if len(transformed_functions) != 1:
        raise BoundaryUnsupported("post_transform_function_resolution")

    transformed_function = transformed_functions[0]

    signature_abstractions: list[str] = []

    inferred_argument_types: list[str] = []

    if transformed_function.args.posonlyargs:
        signature_abstractions.append("POSITIONAL_ONLY_BINDING")

    if transformed_function.args.kwonlyargs:
        signature_abstractions.append("KEYWORD_ONLY_BINDING")

    if transformed_function.args.defaults or transformed_function.args.kw_defaults:
        signature_abstractions.append("DEFAULT_INVOCATION_BINDING")

    positional = [
        *transformed_function.args.posonlyargs,
        *transformed_function.args.args,
        *transformed_function.args.kwonlyargs,
    ]

    transformed_function.args.posonlyargs = []
    transformed_function.args.args = positional
    transformed_function.args.kwonlyargs = []
    transformed_function.args.kw_defaults = []
    transformed_function.args.defaults = []

    if transformed_function.args.vararg is not None:
        vararg_name = transformed_function.args.vararg.arg

        if _loaded_name(
            transformed_function,
            vararg_name,
        ):
            raise BoundaryUnsupported("observed_variadic_positional_binding")

        signature_abstractions.append("UNUSED_VARARG_REMOVED")

        transformed_function.args.vararg = None

    if transformed_function.args.kwarg is not None:
        kwarg_name = transformed_function.args.kwarg.arg

        if _loaded_name(
            transformed_function,
            kwarg_name,
        ):
            raise BoundaryUnsupported("observed_variadic_keyword_binding")

        signature_abstractions.append("UNUSED_KWARG_REMOVED")

        transformed_function.args.kwarg = None

    post_signature_parents = _parent_map(transformed_function)

    for argument in transformed_function.args.args:
        if argument.annotation is not None:
            continue

        inferred = _infer_name_type(
            transformed_function,
            argument.arg,
            post_signature_parents,
        )

        if inferred is None:
            continue

        argument.annotation = ast.Name(
            id=inferred,
            ctx=ast.Load(),
        )

        inferred_argument_types.append(argument.arg + ":" + inferred)

    for binding in transformer.bindings:
        transformed_function.args.args.append(
            ast.arg(
                arg=binding.name,
                annotation=ast.Name(
                    id=binding.type_name,
                    ctx=ast.Load(),
                ),
            )
        )

    ast.fix_missing_locations(transformed_node)

    boundary_names = {binding.name for binding in transformer.bindings}

    semantic_operator_count = _semantic_operator_count(
        transformed_function,
        boundary_names,
    )

    if transformer.bindings and semantic_operator_count == 0:
        raise BoundaryUnsupported("boundary_passthrough_only")

    normalized_source = ast.unparse(transformed_node) + "\n"

    return BoundaryPreparation(
        normalized_source=(normalized_source),
        bindings=tuple(transformer.bindings),
        effects=tuple(transformer.effects),
        signature_abstractions=tuple(signature_abstractions),
        inferred_argument_types=tuple(inferred_argument_types),
        unresolved_calls=tuple(transformer.unresolved_calls),
        unresolved_subscripts=tuple(transformer.unresolved_subscripts),
        semantic_operator_count=(semantic_operator_count),
        source_sha256=source_sha256,
    )


def certify_v014(
    *,
    source_file: Path,
    evidence_id: str,
) -> JsonDict:
    raw = source_file.read_text(encoding="utf-8")

    source_sha256 = _sha256_text(raw)

    try:
        preparation = prepare_boundary_source(source_file=source_file)

    except BoundaryUnsupported as exc:
        return _unsupported_result(
            source_file=source_file,
            source_sha256=(source_sha256),
            reason_code=("v014_boundary_unsupported"),
            reason=str(exc),
        )

    metadata: JsonDict = {
        "bindings": [asdict(binding) for binding in preparation.bindings],
        "effects": list(preparation.effects),
        "signature_abstractions": list(preparation.signature_abstractions),
        "inferred_argument_types": list(preparation.inferred_argument_types),
        "unresolved_calls": list(preparation.unresolved_calls),
        "unresolved_subscripts": list(preparation.unresolved_subscripts),
        "semantic_operator_count": preparation.semantic_operator_count,
        "claim_scope": (
            "formal equivalence of the "
            "boundary-lifted program under "
            "explicit symbolic boundary "
            "bindings; external call, "
            "subscript, decorator, async, "
            "and invocation semantics are "
            "not inferred"
        ),
    }

    with tempfile.TemporaryDirectory(prefix="bizproof-v014-boundary-") as tmp_name:
        transformed_file = Path(tmp_name) / "candidate.py"

        transformed_file.write_text(
            preparation.normalized_source,
            encoding="utf-8",
        )

        try:
            result = certify_universal(
                source_file=(transformed_file),
                evidence_id=evidence_id,
            )

        except Exception as exc:
            return _unsupported_result(
                source_file=source_file,
                source_sha256=(source_sha256),
                reason_code=("v014_downstream_unsupported"),
                reason=(type(exc).__name__ + "::" + str(exc)),
                metadata=metadata,
            )

    result["schema_version"] = "BIZPROOF-V0.14-BOUNDARY-1"

    result["original_source_file"] = str(source_file)

    result["original_source_sha256"] = source_sha256

    result["boundary_lifted_sha256"] = _sha256_text(preparation.normalized_source)

    result["v014_boundary"] = metadata

    capabilities = list(
        result.get(
            "capabilities",
            [],
        )
        or []
    )

    if preparation.bindings:
        capabilities.append("SEMANTIC_BOUNDARY_BINDING")

    if preparation.effects:
        capabilities.append("EXTERNAL_EFFECT_BOUNDARY")

    if preparation.signature_abstractions:
        capabilities.append("INVOCATION_BINDING_ABSTRACTION")

    result["capabilities"] = sorted(set(str(item) for item in capabilities))

    abstraction_active = bool(
        preparation.bindings
        or preparation.effects
        or preparation.signature_abstractions
        or preparation.inferred_argument_types
    )

    if result.get("certified") is True and abstraction_active:
        internal_outcome = result.get("scientific_outcome")

        internal_a2 = int(
            result.get(
                "a2_obligation_count",
                0,
            )
            or 0
        )

        result["boundary_internal_outcome"] = internal_outcome

        result["boundary_internal_a2_obligation_count"] = internal_a2

        result["scientific_outcome"] = "CERTIFIED_A1"

        result["a_level"] = "A1"

        result["a2_obligation_count"] = 0

        result["mutant_refuted_for_a2_claim"] = False

        result["reason_code"] = "v014_parametric_boundary_a1"

        result["reason"] = (
            "certified only under explicit "
            "semantic-boundary abstraction; "
            "external boundary semantics are "
            "not part of the proof"
        )

    return result
