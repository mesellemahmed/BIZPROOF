from __future__ import annotations

import ast
import copy
import hashlib
import tempfile
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .v014_boundary import certify_v014

JsonDict = dict[str, Any]


@dataclass(frozen=True)
class SourceBoundaryBinding:
    name: str
    kind: str
    source_expression: str
    type_name: str


@dataclass(frozen=True)
class Wave4Preparation:
    source: str
    bindings: tuple[SourceBoundaryBinding, ...]
    inferred_locals: tuple[tuple[str, str], ...]
    static_loops_unrolled: int
    static_iterations_unrolled: int
    static_list_comprehensions_expanded: int
    source_sha256: str


def _sha256_text(
    text: str,
) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _annotation_type(
    node: ast.expr | None,
) -> str | None:
    if isinstance(node, ast.Name) and node.id in {"int", "bool"}:
        return node.id

    if isinstance(node, ast.Constant) and node.value in {"int", "bool"}:
        return str(node.value)

    return None


def _parents(
    root: ast.AST,
) -> dict[ast.AST, ast.AST]:
    result: dict[ast.AST, ast.AST] = {}

    for parent in ast.walk(root):
        for child in ast.iter_child_nodes(parent):
            result[child] = parent

    return result


def _static_int(
    node: ast.AST,
) -> int | None:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    ):
        return node.value

    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, int)
        and not isinstance(node.operand.value, bool)
    ):
        return -node.operand.value

    return None


def _static_iterable(
    node: ast.expr,
) -> list[ast.expr] | None:
    if isinstance(
        node,
        (
            ast.Tuple,
            ast.List,
        ),
    ):
        expression_values: list[ast.expr] = []

        for element in node.elts:
            if not (
                isinstance(
                    element,
                    ast.Constant,
                )
                and isinstance(
                    element.value,
                    (
                        int,
                        bool,
                    ),
                )
            ):
                return None

            expression_values.append(copy.deepcopy(element))

        if len(expression_values) > 8:
            return None

        return expression_values

    if (
        isinstance(
            node,
            ast.Call,
        )
        and isinstance(
            node.func,
            ast.Name,
        )
        and node.func.id == "range"
        and not node.keywords
        and 1 <= len(node.args) <= 3
    ):
        parsed = [_static_int(argument) for argument in node.args]

        integer_arguments: list[int] = []

        for value in parsed:
            if value is None:
                return None

            integer_arguments.append(value)

        try:
            integer_values: list[int] = list(range(*integer_arguments))

        except ValueError:
            return None

        if len(integer_values) > 8:
            return None

        return [ast.Constant(value=value) for value in integer_values]

    return None


class _ReplaceLoadedName(
    ast.NodeTransformer,
):
    def __init__(
        self,
        *,
        name: str,
        value: ast.expr,
    ) -> None:
        self._name = name
        self._value = value

    def visit_Name(
        self,
        node: ast.Name,
    ) -> ast.AST:
        if isinstance(node.ctx, ast.Load) and node.id == self._name:
            return ast.copy_location(
                copy.deepcopy(self._value),
                node,
            )

        return node

    def visit_FunctionDef(
        self,
        node: ast.FunctionDef,
    ) -> ast.AST:
        return node

    def visit_AsyncFunctionDef(
        self,
        node: ast.AsyncFunctionDef,
    ) -> ast.AST:
        return node

    def visit_Lambda(
        self,
        node: ast.Lambda,
    ) -> ast.AST:
        return node

    def visit_ClassDef(
        self,
        node: ast.ClassDef,
    ) -> ast.AST:
        return node


class _FiniteStaticLowering(
    ast.NodeTransformer,
):
    def __init__(
        self,
    ) -> None:
        self.loops = 0
        self.iterations = 0
        self.list_comprehensions = 0

    @staticmethod
    def _has_loop_control(
        statements: list[ast.stmt],
    ) -> bool:
        return any(
            isinstance(
                node,
                (
                    ast.Break,
                    ast.Continue,
                ),
            )
            for statement in statements
            for node in ast.walk(statement)
        )

    def visit_For(
        self,
        node: ast.For,
    ) -> ast.AST | list[ast.stmt]:
        node = copy.deepcopy(node)

        if not isinstance(
            node.target,
            ast.Name,
        ):
            return self.generic_visit(node)

        values = _static_iterable(node.iter)

        if values is None:
            return self.generic_visit(node)

        if self._has_loop_control(node.body):
            return self.generic_visit(node)

        expanded: list[ast.stmt] = []

        for value in values:
            assignment = ast.Assign(
                targets=[
                    ast.Name(
                        id=node.target.id,
                        ctx=ast.Store(),
                    )
                ],
                value=copy.deepcopy(value),
            )

            ast.copy_location(
                assignment,
                node,
            )

            expanded.append(assignment)

            for statement in node.body:
                transformed = self.visit(copy.deepcopy(statement))

                if isinstance(
                    transformed,
                    list,
                ):
                    expanded.extend(transformed)

                elif transformed is not None:
                    expanded.append(transformed)

        # Break is forbidden above, therefore Python's for-else suite
        # is executed after every statically expanded iteration.
        for statement in node.orelse:
            transformed = self.visit(copy.deepcopy(statement))

            if isinstance(
                transformed,
                list,
            ):
                expanded.extend(transformed)

            elif transformed is not None:
                expanded.append(transformed)

        self.loops += 1
        self.iterations += len(values)

        return expanded

    def visit_ListComp(
        self,
        node: ast.ListComp,
    ) -> ast.AST:
        if len(node.generators) != 1:
            return self.generic_visit(node)

        generator = node.generators[0]

        if (
            generator.is_async
            or generator.ifs
            or not isinstance(
                generator.target,
                ast.Name,
            )
        ):
            return self.generic_visit(node)

        values = _static_iterable(generator.iter)

        if values is None:
            return self.generic_visit(node)

        if any(
            isinstance(
                child,
                (
                    ast.NamedExpr,
                    ast.Await,
                    ast.Yield,
                    ast.YieldFrom,
                    ast.Lambda,
                ),
            )
            for child in ast.walk(node.elt)
        ):
            return self.generic_visit(node)

        elements: list[ast.expr] = []

        for value in values:
            replacer = _ReplaceLoadedName(
                name=generator.target.id,
                value=value,
            )

            transformed = replacer.visit(copy.deepcopy(node.elt))

            assert isinstance(
                transformed,
                ast.expr,
            )

            transformed = self.visit(transformed)

            assert isinstance(
                transformed,
                ast.expr,
            )

            elements.append(transformed)

        self.list_comprehensions += 1

        return ast.copy_location(
            ast.List(
                elts=elements,
                ctx=ast.Load(),
            ),
            node,
        )


def _expr_type(
    node: ast.AST,
    env: dict[str, str],
) -> str | None:
    if isinstance(
        node,
        ast.Name,
    ):
        return env.get(node.id)

    if isinstance(
        node,
        ast.Constant,
    ):
        if isinstance(
            node.value,
            bool,
        ):
            return "bool"

        if isinstance(
            node.value,
            int,
        ) and not isinstance(
            node.value,
            bool,
        ):
            return "int"

        return None

    if isinstance(
        node,
        ast.Compare,
    ):
        return "bool"

    if isinstance(
        node,
        ast.UnaryOp,
    ):
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

    if isinstance(
        node,
        ast.BoolOp,
    ):
        types = {
            _expr_type(
                value,
                env,
            )
            for value in node.values
        }

        if types == {"bool"}:
            return "bool"

        return None

    if isinstance(
        node,
        ast.BinOp,
    ):
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

    if isinstance(
        node,
        ast.IfExp,
    ):
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

    return None


def _infer_local_types(
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

                annotated = _annotation_type(node.annotation)

                if annotated is not None and env.get(node.target.id) != annotated:
                    env[node.target.id] = annotated

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

            target = node.targets[0].id

            inferred = _expr_type(
                node.value,
                env,
            )

            if inferred is not None and env.get(target) != inferred:
                env[target] = inferred
                changed = True

    return env


def _context_type(
    node: ast.AST,
    *,
    function: ast.FunctionDef,
    parents: dict[
        ast.AST,
        ast.AST,
    ],
    env: dict[str, str],
) -> str | None:
    parent = parents.get(node)

    if parent is None:
        return None

    if isinstance(
        parent,
        ast.Attribute,
    ):
        return None

    if (
        isinstance(
            parent,
            ast.Call,
        )
        and parent.func is node
    ):
        return None

    if isinstance(
        parent,
        ast.Assign,
    ):
        if len(parent.targets) == 1 and isinstance(
            parent.targets[0],
            ast.Name,
        ):
            return env.get(parent.targets[0].id)

    if isinstance(
        parent,
        ast.AnnAssign,
    ):
        return _annotation_type(parent.annotation)

    if isinstance(
        parent,
        ast.Return,
    ):
        return _annotation_type(function.returns)

    if isinstance(
        parent,
        ast.Compare,
    ):
        candidates: set[str] = set()

        expressions: list[ast.expr] = [
            parent.left,
            *parent.comparators,
        ]

        for expression in expressions:
            if expression is node:
                continue

            type_name = _expr_type(
                expression,
                env,
            )

            if type_name is not None:
                candidates.add(type_name)

        if len(candidates) == 1:
            return next(iter(candidates))

        return None

    if isinstance(
        parent,
        ast.BinOp,
    ):
        peer: ast.expr | None = None

        if parent.left is node:
            peer = parent.right

        elif parent.right is node:
            peer = parent.left

        if peer is None:
            return None

        if _expr_type(
            peer,
            env,
        ) == "int" and isinstance(
            parent.op,
            (
                ast.Add,
                ast.Sub,
                ast.Mult,
            ),
        ):
            return "int"

        return None

    if isinstance(
        parent,
        ast.BoolOp,
    ):
        other_types = {
            _expr_type(
                value,
                env,
            )
            for value in parent.values
            if value is not node
        }

        if other_types and other_types == {"bool"}:
            return "bool"

        return None

    return None


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


class _SourceScalarBoundary(
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
        env: dict[str, str],
    ) -> None:
        self._function = function
        self._parents = parents
        self._env = env
        self._locals = _local_names(function)
        self._counter = 0

        self.bindings: list[SourceBoundaryBinding] = []

    def _new(
        self,
        *,
        node: ast.AST,
        kind: str,
        type_name: str,
    ) -> ast.Name:
        self._counter += 1

        name = f"__bp_v014_wave4_{self._counter:04d}"

        self.bindings.append(
            SourceBoundaryBinding(
                name=name,
                kind=kind,
                source_expression=(ast.unparse(node)),
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

        if isinstance(
            parent,
            ast.Attribute,
        ):
            return self.generic_visit(node)

        if (
            isinstance(
                parent,
                ast.Call,
            )
            and parent.func is node
        ):
            return self.generic_visit(node)

        type_name = _context_type(
            node,
            function=self._function,
            parents=self._parents,
            env=self._env,
        )

        if type_name is None:
            return self.generic_visit(node)

        return self._new(
            node=node,
            kind="SOURCE_OPAQUE_ATTRIBUTE",
            type_name=type_name,
        )

    def visit_Subscript(
        self,
        node: ast.Subscript,
    ) -> ast.AST:
        if not isinstance(
            node.ctx,
            ast.Load,
        ):
            return self.generic_visit(node)

        parent = self._parents.get(node)

        if isinstance(
            parent,
            ast.Subscript,
        ):
            return self.generic_visit(node)

        type_name = _context_type(
            node,
            function=self._function,
            parents=self._parents,
            env=self._env,
        )

        if type_name is None:
            return self.generic_visit(node)

        return self._new(
            node=node,
            kind="SOURCE_OPAQUE_SUBSCRIPT",
            type_name=type_name,
        )

    def visit_Call(
        self,
        node: ast.Call,
    ) -> ast.AST:
        # Keep the already supported finite reduction vocabulary.
        if isinstance(node.func, ast.Name) and node.func.id in {
            "all",
            "any",
            "sum",
        }:
            return self.generic_visit(node)

        type_name = _context_type(
            node,
            function=self._function,
            parents=self._parents,
            env=self._env,
        )

        if type_name is None:
            return self.generic_visit(node)

        return self._new(
            node=node,
            kind="SOURCE_OPAQUE_CALL_RESULT",
            type_name=type_name,
        )


def _business_operator_count(
    function: ast.FunctionDef,
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
                ast.For,
                ast.ListComp,
                ast.AugAssign,
            ),
        ):
            count += 1

        elif isinstance(
            node,
            (ast.Assign, ast.AnnAssign),
        ):
            value = getattr(
                node,
                "value",
                None,
            )

            if isinstance(value, ast.Name) and value.id.startswith("__bp_v014_wave4_"):
                continue

            count += 1

    return count


def prepare_wave4_source(
    *,
    source_file: Path,
) -> Wave4Preparation:
    raw = source_file.read_text(encoding="utf-8")

    normalized = textwrap.dedent(raw)

    try:
        tree = ast.parse(normalized)

    except SyntaxError:
        return Wave4Preparation(
            source=normalized,
            bindings=(),
            inferred_locals=(),
            static_loops_unrolled=0,
            static_iterations_unrolled=0,
            static_list_comprehensions_expanded=0,
            source_sha256=_sha256_text(raw),
        )

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
        return Wave4Preparation(
            source=normalized,
            bindings=(),
            inferred_locals=(),
            static_loops_unrolled=0,
            static_iterations_unrolled=0,
            static_list_comprehensions_expanded=0,
            source_sha256=_sha256_text(raw),
        )

    function = functions[0]

    # Preserve decorator semantics by refusing to rewrite them.
    if function.decorator_list:
        return Wave4Preparation(
            source=normalized,
            bindings=(),
            inferred_locals=(),
            static_loops_unrolled=0,
            static_iterations_unrolled=0,
            static_list_comprehensions_expanded=0,
            source_sha256=_sha256_text(raw),
        )

    finite = _FiniteStaticLowering()

    transformed_tree = finite.visit(tree)

    assert isinstance(
        transformed_tree,
        ast.Module,
    )

    ast.fix_missing_locations(transformed_tree)

    transformed_functions = [
        node
        for node in transformed_tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    ]

    assert len(transformed_functions) == 1

    function = transformed_functions[0]

    env = _infer_local_types(function)

    parents = _parents(function)

    boundary = _SourceScalarBoundary(
        function=function,
        parents=parents,
        env=env,
    )

    function.body = [boundary.visit(statement) for statement in function.body]

    # Use required keyword-only parameters. This avoids disturbing
    # existing positional defaults; v014_boundary will normalize the
    # invocation binding in the next layer.
    for binding in boundary.bindings:
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

    ast.fix_missing_locations(transformed_tree)

    source = ast.unparse(transformed_tree) + "\n"

    compile(
        source,
        "<bizproof-v014-wave4>",
        "exec",
    )

    return Wave4Preparation(
        source=source,
        bindings=tuple(boundary.bindings),
        inferred_locals=tuple(sorted(env.items())),
        static_loops_unrolled=(finite.loops),
        static_iterations_unrolled=(finite.iterations),
        static_list_comprehensions_expanded=(finite.list_comprehensions),
        source_sha256=_sha256_text(raw),
    )


def _unsupported_passthrough(
    *,
    source_file: Path,
    preparation: Wave4Preparation,
) -> JsonDict:
    return {
        "schema_version": "BIZPROOF-V0.14-WAVE4-1",
        "source_file": str(source_file),
        "scientific_outcome": "UNSUPPORTED",
        "certified": False,
        "a_level": None,
        "reason_code": "v014_wave4_boundary_passthrough",
        "reason": (
            "source-boundary values exist but no local business operator remains to certify"
        ),
        "formal_obligation_count": 0,
        "a2_obligation_count": 0,
        "v014_wave4": {
            "bindings": [asdict(binding) for binding in preparation.bindings],
            "static_loops_unrolled": preparation.static_loops_unrolled,
            "static_iterations_unrolled": preparation.static_iterations_unrolled,
            "static_list_comprehensions_expanded": preparation.static_list_comprehensions_expanded,
        },
    }


def certify_v014_wave4(
    *,
    source_file: Path,
    evidence_id: str,
) -> JsonDict:
    preparation = prepare_wave4_source(source_file=source_file)

    transformed = bool(
        preparation.bindings
        or preparation.static_loops_unrolled
        or preparation.static_list_comprehensions_expanded
    )

    if not transformed:
        result = certify_v014(
            source_file=source_file,
            evidence_id=evidence_id,
        )

        result["v014_wave4"] = {
            "active": False,
            "bindings": [],
            "static_loops_unrolled": 0,
            "static_iterations_unrolled": 0,
            "static_list_comprehensions_expanded": 0,
        }

        return result

    tree = ast.parse(preparation.source)

    function = next(
        node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    )

    if preparation.bindings and _business_operator_count(function) == 0:
        return _unsupported_passthrough(
            source_file=source_file,
            preparation=preparation,
        )

    with tempfile.TemporaryDirectory(prefix="bizproof-v014-wave4-") as tmp_name:
        candidate = Path(tmp_name) / "candidate.py"

        candidate.write_text(
            preparation.source,
            encoding="utf-8",
        )

        result = certify_v014(
            source_file=candidate,
            evidence_id=evidence_id,
        )

    result["v014_wave4"] = {
        "active": True,
        "bindings": [asdict(binding) for binding in preparation.bindings],
        "inferred_locals": [
            {
                "name": name,
                "type_name": type_name,
            }
            for name, type_name in preparation.inferred_locals
        ],
        "static_loops_unrolled": preparation.static_loops_unrolled,
        "static_iterations_unrolled": preparation.static_iterations_unrolled,
        "static_list_comprehensions_expanded": preparation.static_list_comprehensions_expanded,
        "source_sha256": preparation.source_sha256,
        "transformed_sha256": _sha256_text(preparation.source),
        "claim_scope": (
            "A1 maximum after source-level boundary abstraction or exact statically finite lowering"
        ),
    }

    if result.get("certified") is True:
        result["v014_wave4_internal_outcome"] = result.get("scientific_outcome")

        result["scientific_outcome"] = "CERTIFIED_A1"

        result["a_level"] = "A1"

        result["a2_obligation_count"] = 0

        result["reason_code"] = "v014_wave4_a1"

        result["reason"] = (
            "certified after generic V0.14 Wave4 lowering; claim conservatively capped at A1"
        )

    return result
