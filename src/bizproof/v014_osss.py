from __future__ import annotations

import ast
import copy
import hashlib
import tempfile
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .v014_highcoverage import (
    certify_v014_wave4,
)

JsonDict = dict[str, Any]


@dataclass(frozen=True)
class SliceMetadata:
    observation_kind: str
    observation_type: str
    relevant_statement_count: int
    removed_statement_count: int
    relevant_names: tuple[str, ...]
    source_sha256: str
    sliced_sha256: str


@dataclass(frozen=True)
class SlicePreparation:
    source: str
    metadata: SliceMetadata


class SliceUnsupported(RuntimeError):
    pass


UNSUPPORTED_ON_SLICE = (
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.Raise,
    ast.Yield,
    ast.YieldFrom,
    ast.Await,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.Lambda,
)


def _sha256_text(
    value: str,
) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _annotation_type(
    annotation: ast.expr | None,
) -> str | None:
    if isinstance(annotation, ast.Name) and annotation.id in {
        "int",
        "bool",
    }:
        return annotation.id

    if isinstance(annotation, ast.Constant) and annotation.value in {
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


def _loaded_names(
    node: ast.AST,
) -> set[str]:
    return {
        child.id
        for child in ast.walk(node)
        if (
            isinstance(child, ast.Name)
            and isinstance(
                child.ctx,
                ast.Load,
            )
        )
    }


def _direct_defined_names(
    statement: ast.stmt,
) -> set[str]:
    result: set[str] = set()

    if isinstance(statement, ast.Assign):
        for target in statement.targets:
            if isinstance(
                target,
                ast.Name,
            ):
                result.add(target.id)

    elif isinstance(
        statement,
        ast.AnnAssign,
    ):
        if isinstance(
            statement.target,
            ast.Name,
        ):
            result.add(statement.target.id)

    elif isinstance(
        statement,
        ast.AugAssign,
    ):
        if isinstance(
            statement.target,
            ast.Name,
        ):
            result.add(statement.target.id)

    return result


def _expr_type(
    node: ast.AST,
    env: dict[str, str],
) -> str | None:
    if isinstance(node, ast.Name):
        return env.get(node.id)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "bool"

        if isinstance(node.value, int) and not isinstance(
            node.value,
            bool,
        ):
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
                    ast.USub,
                    ast.UAdd,
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

                type_name = _annotation_type(node.annotation)

                if type_name is not None and env.get(node.target.id) != type_name:
                    env[node.target.id] = type_name

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


def _resolve_function(
    tree: ast.Module,
) -> ast.FunctionDef:
    functions = [
        node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    ]

    if len(functions) != 1:
        raise SliceUnsupported("slice_requires_exactly_one_top_level_sync_function")

    function = functions[0]

    if function.decorator_list:
        raise SliceUnsupported("decorator_semantics_not_sliced")

    return function


def _statement_parent(
    node: ast.AST,
    parent_map: dict[
        ast.AST,
        ast.AST,
    ],
) -> ast.stmt | None:
    current: ast.AST | None = node

    while current is not None:
        if isinstance(
            current,
            ast.stmt,
        ):
            return current

        current = parent_map.get(current)

    return None


def _control_ancestors(
    statement: ast.stmt,
    parent_map: dict[
        ast.AST,
        ast.AST,
    ],
) -> list[ast.stmt]:
    result: list[ast.stmt] = []

    current: ast.AST | None = parent_map.get(statement)

    while current is not None:
        if isinstance(
            current,
            ast.If,
        ):
            result.append(current)

        elif isinstance(
            current,
            (
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.Try,
                ast.With,
                ast.AsyncWith,
            ),
        ):
            raise SliceUnsupported("dynamic_control_on_observation_slice:" + type(current).__name__)

        current = parent_map.get(current)

    return result


def _direct_definitions(
    function: ast.FunctionDef,
) -> dict[
    str,
    list[ast.stmt],
]:
    result: dict[
        str,
        list[ast.stmt],
    ] = {}

    for node in ast.walk(function):
        if not isinstance(
            node,
            ast.stmt,
        ):
            continue

        for name in _direct_defined_names(node):
            result.setdefault(
                name,
                [],
            ).append(node)

    return result


def _observation_type(
    function: ast.FunctionDef,
    env: dict[str, str],
) -> tuple[
    str,
    list[ast.Return],
]:
    returns = [
        node
        for node in ast.walk(function)
        if isinstance(
            node,
            ast.Return,
        )
    ]

    if not returns:
        raise SliceUnsupported("no_return_observation")

    if any(node.value is None for node in returns):
        raise SliceUnsupported("non_value_return_on_observation")

    annotated = _annotation_type(function.returns)

    if annotated is not None:
        return (
            annotated,
            returns,
        )

    inferred = {
        _expr_type(
            node.value,
            env,
        )
        for node in returns
        if node.value is not None
    }

    inferred.discard(None)

    if len(inferred) != 1:
        raise SliceUnsupported("scalar_return_type_not_unique")

    type_name = next(iter(inferred))

    if type_name not in {
        "int",
        "bool",
    }:
        raise SliceUnsupported("non_scalar_return_observation")

    return (
        type_name,
        returns,
    )


def _compute_slice(
    function: ast.FunctionDef,
) -> tuple[
    str,
    set[int],
    set[str],
]:
    env = _infer_types(function)

    (
        observation_type,
        returns,
    ) = _observation_type(
        function,
        env,
    )

    parent_map = _parents(function)

    definitions = _direct_definitions(function)

    relevant_statements: set[int] = set()

    relevant_names: set[str] = set()

    pending_names: list[str] = []

    pending_statements: list[ast.stmt] = []

    def add_name(
        name: str,
    ) -> None:
        if name in relevant_names:
            return

        relevant_names.add(name)
        pending_names.append(name)

    def add_statement(
        statement: ast.stmt,
    ) -> None:
        if id(statement) in (relevant_statements):
            return

        relevant_statements.add(id(statement))

        pending_statements.append(statement)

        for ancestor in _control_ancestors(
            statement,
            parent_map,
        ):
            if id(ancestor) not in (relevant_statements):
                relevant_statements.add(id(ancestor))

                pending_statements.append(ancestor)

    for return_node in returns:
        add_statement(return_node)

        assert return_node.value is not None

        for name in _loaded_names(return_node.value):
            add_name(name)

    processed_names: set[str] = set()

    while pending_names or pending_statements:
        while pending_names:
            name = pending_names.pop()

            if name in processed_names:
                continue

            processed_names.add(name)

            for definition in definitions.get(name, []):
                add_statement(definition)

                for dependency in _loaded_names(definition):
                    add_name(dependency)

        while pending_statements:
            statement = pending_statements.pop()

            if isinstance(
                statement,
                ast.If,
            ):
                for dependency in _loaded_names(statement.test):
                    add_name(dependency)

            for node in ast.walk(statement):
                if (
                    isinstance(
                        node,
                        UNSUPPORTED_ON_SLICE,
                    )
                    and node is not statement
                ):
                    raise SliceUnsupported(
                        "unsupported_construct_on_observation_slice:" + type(node).__name__
                    )

    return (
        observation_type,
        relevant_statements,
        relevant_names,
    )


def _marker() -> ast.Expr:
    return ast.Expr(value=ast.Constant(value=("BIZPROOF_OSSS_NOOP")))


def _slice_body(
    statements: list[ast.stmt],
    relevant: set[int],
) -> list[ast.stmt]:
    result: list[ast.stmt] = []

    for statement in statements:
        if isinstance(
            statement,
            ast.If,
        ):
            if id(statement) not in relevant:
                continue

            cloned = copy.deepcopy(statement)

            cloned.body = _slice_body(
                statement.body,
                relevant,
            )

            cloned.orelse = _slice_body(
                statement.orelse,
                relevant,
            )

            if not cloned.body:
                cloned.body = [_marker()]

            if statement.orelse and not cloned.orelse:
                cloned.orelse = [_marker()]

            result.append(cloned)

            continue

        if id(statement) in relevant:
            result.append(copy.deepcopy(statement))

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


def _verify_no_relevant_structured_mutation(
    function: ast.FunctionDef,
    relevant_names: set[str],
    relevant_statements: set[int],
) -> None:
    parent_map = _parents(function)

    for node in ast.walk(function):
        if not isinstance(
            node,
            (
                ast.Attribute,
                ast.Subscript,
            ),
        ):
            continue

        if not isinstance(
            node.ctx,
            ast.Store,
        ):
            continue

        root = _root_name(node)

        if root is None or root not in relevant_names:
            continue

        statement = _statement_parent(
            node,
            parent_map,
        )

        if statement is None or id(statement) not in relevant_statements:
            raise SliceUnsupported("off_slice_mutation_of_relevant_structured_state:" + root)


def prepare_osss_source(
    *,
    source_file: Path,
) -> SlicePreparation:
    raw = source_file.read_text(encoding="utf-8")

    normalized = textwrap.dedent(raw)

    tree = ast.parse(normalized)

    function = _resolve_function(tree)

    (
        observation_type,
        relevant,
        relevant_names,
    ) = _compute_slice(function)

    _verify_no_relevant_structured_mutation(
        function,
        relevant_names,
        relevant,
    )

    sliced_function = copy.deepcopy(function)

    sliced_function.body = _slice_body(
        function.body,
        relevant,
    )

    if not sliced_function.body:
        raise SliceUnsupported("empty_observation_slice")

    if sliced_function.returns is None:
        sliced_function.returns = ast.Name(
            id=observation_type,
            ctx=ast.Load(),
        )

    sliced_function.decorator_list = []

    sliced_module = ast.Module(
        body=[sliced_function],
        type_ignores=[],
    )

    ast.fix_missing_locations(sliced_module)

    source = ast.unparse(sliced_module) + "\n"

    compile(
        source,
        "<bizproof-osss>",
        "exec",
    )

    original_statement_count = sum(
        isinstance(
            node,
            ast.stmt,
        )
        for node in ast.walk(function)
    )

    sliced_statement_count = sum(
        isinstance(
            node,
            ast.stmt,
        )
        for node in ast.walk(sliced_function)
    )

    metadata = SliceMetadata(
        observation_kind=("SCALAR_RETURN"),
        observation_type=(observation_type),
        relevant_statement_count=(len(relevant)),
        removed_statement_count=max(
            0,
            original_statement_count - sliced_statement_count,
        ),
        relevant_names=tuple(sorted(relevant_names)),
        source_sha256=_sha256_text(raw),
        sliced_sha256=_sha256_text(source),
    )

    return SlicePreparation(
        source=source,
        metadata=metadata,
    )


def certify_v014_osss(
    *,
    source_file: Path,
    evidence_id: str,
) -> JsonDict:
    try:
        preparation = prepare_osss_source(source_file=source_file)

    except (
        SyntaxError,
        SliceUnsupported,
    ) as exc:
        # OSSS is an additive capability. If no safe scalar slice can
        # be constructed, preserve the existing Wave4 behavior.
        result = certify_v014_wave4(
            source_file=source_file,
            evidence_id=evidence_id,
        )

        result["v014_osss"] = {
            "active": False,
            "reason": (type(exc).__name__ + "::" + str(exc)),
        }

        return result

    with tempfile.TemporaryDirectory(prefix="bizproof-v014-osss-") as tmp_name:
        candidate = Path(tmp_name) / "candidate.py"

        candidate.write_text(
            preparation.source,
            encoding="utf-8",
        )

        result = certify_v014_wave4(
            source_file=candidate,
            evidence_id=evidence_id,
        )

    result["v014_osss"] = {
        "active": True,
        **asdict(preparation.metadata),
        "claim_scope": (
            "A1 observation-scoped parametric "
            "equivalence for the selected scalar "
            "return slice, conditional on explicit "
            "boundary observations. No equivalence "
            "claim is made for removed statements "
            "or whole-program effects."
        ),
    }

    if result.get("certified") is True:
        result["v014_osss_internal_outcome"] = result.get("scientific_outcome")

        result["scientific_outcome"] = "CERTIFIED_A1"

        result["a_level"] = "A1"

        result["a2_obligation_count"] = 0

        result["reason_code"] = "v014_osss_a1"

        result["reason"] = (
            "scalar business observation certified "
            "under conservative semantic slicing "
            "and explicit boundary valuations"
        )

    return result
