from __future__ import annotations

import ast
import hashlib
import tempfile
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .v014_obligation import (
    certify_obligation_v014 as certify_previous,
)

JsonDict = dict[str, Any]


@dataclass(frozen=True)
class LocalTypeBinding:
    name: str
    kind: str
    source_expression: str
    type_name: str


@dataclass(frozen=True)
class LocalTypePreparation:
    source: str
    bindings: tuple[LocalTypeBinding, ...]
    inferred_locals: tuple[tuple[str, str], ...]
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


def _parents(
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
        ast.BoolOp,
    ):
        types = {
            _expr_type(
                value,
                env,
            )
            for value in node.values
        }

        if types == {
            "bool",
        }:
            return "bool"

        return None

    if isinstance(
        node,
        ast.UnaryOp,
    ):
        inner = _expr_type(
            node.operand,
            env,
        )

        if isinstance(
            node.op,
            ast.Not,
        ):
            if inner == "bool":
                return "bool"

            return None

        if isinstance(
            node.op,
            (
                ast.UAdd,
                ast.USub,
            ),
        ):
            if inner == "int":
                return "int"

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
        body = _expr_type(
            node.body,
            env,
        )

        other = _expr_type(
            node.orelse,
            env,
        )

        if body is not None and body == other:
            return body

    return None


def _infer_local_types(
    function: ast.FunctionDef,
) -> dict[str, str]:
    env: dict[
        str,
        str,
    ] = {}

    for argument in function.args.args:
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
    node: ast.Attribute,
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

    # Do not transform an inner part of x.y.z.
    if isinstance(
        parent,
        ast.Attribute,
    ):
        return None

    # Do not reinterpret a method callee as a value.
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
        other: ast.expr | None = None

        if parent.left is node:
            other = parent.right

        elif parent.right is node:
            other = parent.left

        if other is None:
            return None

        other_type = _expr_type(
            other,
            env,
        )

        if other_type == "int" and isinstance(
            parent.op,
            (
                ast.Add,
                ast.Sub,
                ast.Mult,
            ),
        ):
            return "int"

        # No string inference.
        return None

    return None


class _LocalTypeLift(
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

        self._counter = 0

        self.bindings: list[LocalTypeBinding] = []

    def _new_binding(
        self,
        *,
        node: ast.Attribute,
        type_name: str,
    ) -> ast.Name:
        self._counter += 1

        name = f"__bp_v014_localtype_{self._counter:04d}"

        self.bindings.append(
            LocalTypeBinding(
                name=name,
                kind=("FORMAL_TYPED_EXTERNAL_ATTRIBUTE"),
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

        type_name = _context_type(
            node,
            function=self._function,
            parents=self._parents,
            env=self._env,
        )

        if type_name is None:
            return self.generic_visit(node)

        return self._new_binding(
            node=node,
            type_name=type_name,
        )


def prepare_localtype_obligation(
    *,
    source_file: Path,
) -> LocalTypePreparation:
    raw = source_file.read_text(encoding="utf-8")

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
        return LocalTypePreparation(
            source=normalized,
            bindings=(),
            inferred_locals=(),
            source_sha256=(_sha256_text(raw)),
        )

    function = functions[0]

    env = _infer_local_types(function)

    parents = _parents(function)

    transformer = _LocalTypeLift(
        function=function,
        parents=parents,
        env=env,
    )

    function.body = [transformer.visit(statement) for statement in function.body]

    for binding in transformer.bindings:
        function.args.args.append(
            ast.arg(
                arg=binding.name,
                annotation=ast.Name(
                    id=binding.type_name,
                    ctx=ast.Load(),
                ),
            )
        )

    ast.fix_missing_locations(tree)

    source = ast.unparse(tree) + "\n"

    compile(
        source,
        "<v014-localtype-obligation>",
        "exec",
    )

    return LocalTypePreparation(
        source=source,
        bindings=tuple(transformer.bindings),
        inferred_locals=tuple(sorted(env.items())),
        source_sha256=(_sha256_text(raw)),
    )


def certify_obligation_v014_localtypes(
    *,
    source_file: Path,
    case_id: str,
) -> JsonDict:
    preparation = prepare_localtype_obligation(source_file=source_file)

    with tempfile.TemporaryDirectory(prefix="bizproof-v014-localtype-") as tmp_name:
        candidate = Path(tmp_name) / "candidate.py"

        candidate.write_text(
            preparation.source,
            encoding="utf-8",
        )

        result = certify_previous(
            source_file=candidate,
            case_id=case_id,
        )

    metadata = {
        "bindings": [asdict(binding) for binding in preparation.bindings],
        "inferred_locals": [
            {
                "name": name,
                "type_name": type_name,
            }
            for name, type_name in preparation.inferred_locals
        ],
        "source_sha256": preparation.source_sha256,
        "transformed_sha256": _sha256_text(preparation.source),
        "claim_scope": (
            "external attributes are lifted "
            "only when an existing local "
            "int/bool typing context uniquely "
            "determines their abstract scalar sort"
        ),
    }

    result["v014_localtype_boundary"] = metadata

    if preparation.bindings and result.get("certified") is True:
        result["v014_pre_localtype_outcome"] = result.get("scientific_outcome")

        result["scientific_outcome"] = "CERTIFIED_A1"

        result["a_level"] = "A1"

        result["reason_code"] = "v014_localtype_boundary_a1"

        result["reason"] = "proved under explicit typed external-attribute bindings"

    return result
