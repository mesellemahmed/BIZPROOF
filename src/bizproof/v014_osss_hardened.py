from __future__ import annotations

import ast
import copy
import hashlib
import tempfile
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .universal_closure import certify_universal
from .v014_boundary import (
    BoundaryUnsupported,
    prepare_boundary_source,
)
from .v014_highcoverage import (
    certify_v014_wave4,
    prepare_wave4_source,
)
from .v014_osss import (
    SliceUnsupported,
    prepare_osss_source,
)

JsonDict = dict[str, Any]


class HardenedOsssUnsupported(
    RuntimeError,
):
    pass


@dataclass(frozen=True)
class EqualityToken:
    name: str
    source_expression: str
    type_name: str


@dataclass(frozen=True)
class EqualityPreparation:
    source: str
    bindings: tuple[EqualityToken, ...]


def _sha256_text(
    value: str,
) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _annotation_type(
    node: ast.expr | None,
) -> str | None:
    if isinstance(node, ast.Name) and node.id in {"int", "bool"}:
        return node.id

    if isinstance(node, ast.Constant) and node.value in {"int", "bool"}:
        return str(node.value)

    return None


def _expr_type(
    node: ast.AST,
    env: dict[str, str],
) -> str | None:
    if isinstance(node, ast.Name):
        return env.get(node.id)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "bool"

        if isinstance(node.value, int) and not isinstance(node.value, bool):
            return "int"

        return None

    if isinstance(node, ast.Compare):
        return "bool"

    if isinstance(node, ast.BoolOp):
        values = {
            _expr_type(
                value,
                env,
            )
            for value in node.values
        }

        if values == {"bool"}:
            return "bool"

        return None

    if isinstance(node, ast.UnaryOp):
        inner = _expr_type(
            node.operand,
            env,
        )

        if isinstance(node.op, ast.Not) and inner == "bool":
            return "bool"

        if (
            isinstance(
                node.op,
                (
                    ast.UAdd,
                    ast.USub,
                ),
            )
            and inner == "int"
        ):
            return "int"

        return None

    if isinstance(node, ast.BinOp):
        left = _expr_type(
            node.left,
            env,
        )

        right = _expr_type(
            node.right,
            env,
        )

        if (
            left == "int"
            and right == "int"
            and isinstance(
                node.op,
                (
                    ast.Add,
                    ast.Sub,
                    ast.Mult,
                ),
            )
        ):
            return "int"

        return None

    if isinstance(node, ast.IfExp):
        left = _expr_type(
            node.body,
            env,
        )

        right = _expr_type(
            node.orelse,
            env,
        )

        if left is not None and left == right:
            return left

        return None

    if isinstance(node, ast.Call):
        if isinstance(
            node.func,
            ast.Name,
        ):
            if node.func.id in {
                "bool",
                "any",
                "all",
            }:
                return "bool"

            if node.func.id == "len":
                return "int"

    return None


def _infer_types(
    function: ast.FunctionDef,
) -> dict[str, str]:
    env: dict[str, str] = {}

    for argument in [
        *function.args.posonlyargs,
        *function.args.args,
        *function.args.kwonlyargs,
    ]:
        type_name = _annotation_type(argument.annotation)

        if type_name is not None:
            env[argument.arg] = type_name

    changed = True

    while changed:
        changed = False

        for node in ast.walk(function):
            if isinstance(
                node,
                ast.AnnAssign,
            ):
                if not isinstance(
                    node.target,
                    ast.Name,
                ):
                    continue

                inferred = _annotation_type(node.annotation)

                if inferred is not None and env.get(node.target.id) != inferred:
                    env[node.target.id] = inferred

                    changed = True

                continue

            if not isinstance(
                node,
                ast.Assign,
            ):
                continue

            if len(node.targets) != 1 or not isinstance(
                node.targets[0],
                ast.Name,
            ):
                continue

            inferred = _expr_type(
                node.value,
                env,
            )

            if inferred is not None and env.get(node.targets[0].id) != inferred:
                env[node.targets[0].id] = inferred

                changed = True

    return env


class _ReturnCollector(
    ast.NodeVisitor,
):
    def __init__(self) -> None:
        self.returns: list[ast.Return] = []

        self._root_seen = False

    def visit_FunctionDef(
        self,
        node: ast.FunctionDef,
    ) -> None:
        if self._root_seen:
            return

        self._root_seen = True

        for statement in node.body:
            self.visit(statement)

    def visit_AsyncFunctionDef(
        self,
        node: ast.AsyncFunctionDef,
    ) -> None:
        return

    def visit_Lambda(
        self,
        node: ast.Lambda,
    ) -> None:
        return

    def visit_Return(
        self,
        node: ast.Return,
    ) -> None:
        self.returns.append(node)


def _resolve_function(
    source: str,
) -> ast.FunctionDef:
    tree = ast.parse(textwrap.dedent(source))

    functions = [
        node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    ]

    async_functions = [
        node
        for node in tree.body
        if isinstance(
            node,
            ast.AsyncFunctionDef,
        )
    ]

    if len(functions) != 1 or async_functions:
        raise HardenedOsssUnsupported("strict_observation_requires_one_sync_function")

    return functions[0]


def _strict_observation_type(
    *,
    source_file: Path,
) -> str:
    raw = source_file.read_text(encoding="utf-8")

    function = _resolve_function(raw)

    if function.returns is not None:
        annotated = _annotation_type(function.returns)

        if annotated is None:
            raise HardenedOsssUnsupported(
                "non_scalar_return_annotation:" + ast.unparse(function.returns)
            )

        return annotated

    env = _infer_types(function)

    collector = _ReturnCollector()
    collector.visit(function)

    returns = collector.returns

    if not returns:
        raise HardenedOsssUnsupported("no_return_observation")

    types: list[str] = []

    for node in returns:
        if node.value is None:
            raise HardenedOsssUnsupported("none_return_observation")

        inferred = _expr_type(
            node.value,
            env,
        )

        if inferred not in {
            "int",
            "bool",
        }:
            raise HardenedOsssUnsupported(
                "unknown_return_expression_type:" + ast.unparse(node.value)
            )

        types.append(inferred)

    unique = set(types)

    if len(unique) != 1:
        raise HardenedOsssUnsupported("mixed_scalar_return_types")

    return next(iter(unique))


def _local_names(
    function: ast.FunctionDef,
) -> set[str]:
    result = {
        argument.arg
        for argument in [
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        ]
    }

    if function.args.vararg is not None:
        result.add(function.args.vararg.arg)

    if function.args.kwarg is not None:
        result.add(function.args.kwarg.arg)

    for node in ast.walk(function):
        if isinstance(node, ast.Name) and isinstance(
            node.ctx,
            ast.Store,
        ):
            result.add(node.id)

    return result


def _is_opaque_equality_operand(
    node: ast.expr,
    local_names: set[str],
) -> bool:
    if isinstance(
        node,
        (
            ast.Attribute,
            ast.Call,
            ast.Subscript,
        ),
    ):
        return True

    if isinstance(node, ast.Name):
        return node.id not in local_names and node.id not in {
            "True",
            "False",
        }

    return False


class _EqualityLift(
    ast.NodeTransformer,
):
    def __init__(
        self,
        *,
        function: ast.FunctionDef,
    ) -> None:
        self._env = _infer_types(function)

        self._locals = _local_names(function)

        self._counter = 0

        self._by_expression: dict[
            str,
            EqualityToken,
        ] = {}

        self.bindings: list[EqualityToken] = []

    def _binding(
        self,
        node: ast.expr,
        type_name: str,
    ) -> ast.Name:
        expression = ast.unparse(node)

        existing = self._by_expression.get(expression)

        if existing is not None:
            return ast.copy_location(
                ast.Name(
                    id=existing.name,
                    ctx=ast.Load(),
                ),
                node,
            )

        self._counter += 1

        name = f"__bp_v014_eqtoken_{self._counter:04d}"

        binding = EqualityToken(
            name=name,
            source_expression=expression,
            type_name=type_name,
        )

        self._by_expression[expression] = binding

        self.bindings.append(binding)

        return ast.copy_location(
            ast.Name(
                id=name,
                ctx=ast.Load(),
            ),
            node,
        )

    def visit_Compare(
        self,
        node: ast.Compare,
    ) -> ast.AST:
        if not all(
            isinstance(
                operator,
                (
                    ast.Eq,
                    ast.NotEq,
                ),
            )
            for operator in node.ops
        ):
            return self.generic_visit(node)

        expressions: list[ast.expr] = [
            node.left,
            *node.comparators,
        ]

        inferred = [
            _expr_type(
                expression,
                self._env,
            )
            for expression in expressions
        ]

        known = {type_name for type_name in inferred if type_name is not None}

        if len(known) > 1:
            return self.generic_visit(node)

        if known:
            token_type = next(iter(known))

        else:
            if not all(
                _is_opaque_equality_operand(
                    expression,
                    self._locals,
                )
                for expression in expressions
            ):
                return self.generic_visit(node)

            # Int is used here only as the carrier sort for an opaque
            # equality token. No numeric ordering/arithmetic semantics
            # are claimed.
            token_type = "int"

        transformed: list[ast.expr] = []

        changed = False

        for expression, type_name in zip(
            expressions,
            inferred,
            strict=True,
        ):
            if type_name is not None:
                transformed.append(expression)
                continue

            if not _is_opaque_equality_operand(
                expression,
                self._locals,
            ):
                return self.generic_visit(node)

            transformed.append(
                self._binding(
                    expression,
                    token_type,
                )
            )

            changed = True

        if not changed:
            return self.generic_visit(node)

        node.left = transformed[0]
        node.comparators = transformed[1:]

        return node


def _prepare_equality_tokens(
    *,
    source: str,
) -> EqualityPreparation:
    tree = ast.parse(textwrap.dedent(source))

    functions = [
        node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    ]

    if len(functions) != 1:
        raise HardenedOsssUnsupported("equality_lift_function_resolution")

    function = functions[0]

    transformer = _EqualityLift(function=function)

    function.body = [transformer.visit(statement) for statement in function.body]

    for binding in transformer.bindings:
        function.args.kwonlyargs.append(
            ast.arg(
                arg=binding.name,
                annotation=ast.Name(
                    id=binding.type_name,
                    ctx=ast.Load(),
                ),
            )
        )

        function.args.kw_defaults.append(None)

    ast.fix_missing_locations(tree)

    transformed = ast.unparse(tree) + "\n"

    compile(
        transformed,
        "<bizproof-osss-equality>",
        "exec",
    )

    return EqualityPreparation(
        source=transformed,
        bindings=tuple(transformer.bindings),
    )


def _loaded_names(
    function: ast.FunctionDef,
) -> set[str]:
    return {
        node.id
        for node in ast.walk(function)
        if (
            isinstance(
                node,
                ast.Name,
            )
            and isinstance(
                node.ctx,
                ast.Load,
            )
        )
    }


def _dead_assignment_target(
    statement: ast.stmt,
) -> str | None:
    if isinstance(
        statement,
        ast.Assign,
    ):
        if len(statement.targets) == 1 and isinstance(
            statement.targets[0],
            ast.Name,
        ):
            return statement.targets[0].id

    if isinstance(
        statement,
        ast.AnnAssign,
    ):
        if isinstance(
            statement.target,
            ast.Name,
        ):
            return statement.target.id

    return None


def _marker() -> ast.Expr:
    return ast.Expr(value=ast.Constant(value="BIZPROOF_OSSS_PRUNED_NOOP"))


def _prune_block(
    statements: list[ast.stmt],
    *,
    loaded: set[str],
    removed: list[str],
) -> list[ast.stmt]:
    result: list[ast.stmt] = []

    for statement in statements:
        target = _dead_assignment_target(statement)

        if target is not None and target not in loaded:
            removed.append(ast.unparse(statement))

            continue

        if isinstance(
            statement,
            ast.If,
        ):
            cloned = copy.deepcopy(statement)

            cloned.body = _prune_block(
                statement.body,
                loaded=loaded,
                removed=removed,
            )

            cloned.orelse = _prune_block(
                statement.orelse,
                loaded=loaded,
                removed=removed,
            )

            if not cloned.body:
                cloned.body = [_marker()]

            if statement.orelse and not cloned.orelse:
                cloned.orelse = [_marker()]

            result.append(cloned)

            continue

        result.append(copy.deepcopy(statement))

    return result


def _prune_dead_producers(
    source: str,
) -> tuple[
    str,
    tuple[str, ...],
]:
    tree = ast.parse(textwrap.dedent(source))

    functions = [
        node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    ]

    if len(functions) != 1:
        raise HardenedOsssUnsupported("dead_prune_function_resolution")

    function = functions[0]

    removed: list[str] = []

    changed = True

    while changed:
        changed = False

        loaded = _loaded_names(function)

        before = len(removed)

        function.body = _prune_block(
            function.body,
            loaded=loaded,
            removed=removed,
        )

        if len(removed) > before:
            changed = True

    ast.fix_missing_locations(tree)

    transformed = ast.unparse(tree) + "\n"

    compile(
        transformed,
        "<bizproof-osss-pruned>",
        "exec",
    )

    return (
        transformed,
        tuple(removed),
    )


def _business_operator_count(
    source: str,
) -> int:
    tree = ast.parse(source)

    count = 0

    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.Compare,
                ast.BinOp,
                ast.BoolOp,
                ast.If,
                ast.IfExp,
            ),
        ):
            count += 1

        elif isinstance(
            node,
            ast.UnaryOp,
        ) and isinstance(
            node.op,
            ast.Not,
        ):
            count += 1

    return count


def _fallback(
    *,
    source_file: Path,
    evidence_id: str,
    reason: str,
) -> JsonDict:
    result = certify_v014_wave4(
        source_file=source_file,
        evidence_id=evidence_id,
    )

    result["v014_osss_hardened"] = {
        "active": False,
        "reason": reason,
    }

    return result


def certify_v014_osss_hardened(
    *,
    source_file: Path,
    evidence_id: str,
) -> JsonDict:
    try:
        strict_type = _strict_observation_type(source_file=source_file)

        slice_preparation = prepare_osss_source(source_file=source_file)

        equality = _prepare_equality_tokens(source=(slice_preparation.source))

        with tempfile.TemporaryDirectory(prefix="bizproof-v014-wave5d-") as tmp_name:
            tmp = Path(tmp_name)

            equality_file = tmp / "01_equality.py"

            equality_file.write_text(
                equality.source,
                encoding="utf-8",
            )

            wave4 = prepare_wave4_source(source_file=equality_file)

            wave4_active = bool(
                wave4.bindings
                or wave4.static_loops_unrolled
                or wave4.static_list_comprehensions_expanded
            )

            if wave4_active:
                boundary_input = wave4.source

            else:
                boundary_input = equality.source

            boundary_input_file = tmp / "02_boundary_input.py"

            boundary_input_file.write_text(
                boundary_input,
                encoding="utf-8",
            )

            boundary = prepare_boundary_source(source_file=(boundary_input_file))

            (
                pruned_source,
                removed_producers,
            ) = _prune_dead_producers(boundary.normalized_source)

            operator_count = _business_operator_count(pruned_source)

            if operator_count <= 0:
                return _fallback(
                    source_file=source_file,
                    evidence_id=evidence_id,
                    reason=("observation reduces to pure semantic-boundary passthrough"),
                )

            pruned_file = tmp / "03_pruned_observation.py"

            pruned_file.write_text(
                pruned_source,
                encoding="utf-8",
            )

            result = certify_universal(
                source_file=pruned_file,
                evidence_id=evidence_id,
            )

    except (
        BoundaryUnsupported,
        HardenedOsssUnsupported,
        SliceUnsupported,
        SyntaxError,
        ValueError,
    ) as exc:
        return _fallback(
            source_file=source_file,
            evidence_id=evidence_id,
            reason=(type(exc).__name__ + "::" + str(exc)),
        )

    metadata = {
        "active": True,
        "strict_observation_type": strict_type,
        "observation_kind": slice_preparation.metadata.observation_kind,
        "equality_tokens": [asdict(binding) for binding in equality.bindings],
        "wave4_bindings": [asdict(binding) for binding in wave4.bindings],
        "boundary_bindings": [asdict(binding) for binding in boundary.bindings],
        "removed_dead_producers": list(removed_producers),
        "business_operator_count": operator_count,
        "pruned_sha256": _sha256_text(pruned_source),
        "claim_scope": (
            "A1 observation-scoped parametric "
            "equivalence. Opaque equality tokens "
            "are valid only under valuations that "
            "preserve equality/inequality of the "
            "corresponding runtime observations. "
            "Removed producer effects and whole-"
            "program behavior are outside the claim."
        ),
    }

    result["v014_osss_hardened"] = metadata

    if result.get("certified") is True:
        result["v014_osss_hardened_internal_outcome"] = result.get("scientific_outcome")

        result["scientific_outcome"] = "CERTIFIED_A1"

        result["a_level"] = "A1"

        result["a2_obligation_count"] = 0

        result["reason_code"] = "v014_osss_hardened_a1"

        result["reason"] = (
            "scalar observation certified after "
            "strict slicing, explicit boundary "
            "abstraction and removal of producers "
            "that are dead with respect to the "
            "certified observation"
        )

    return result
