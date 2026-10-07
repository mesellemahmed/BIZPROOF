from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import tempfile
import textwrap
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from .model import BusinessContract, InputSpec, TargetSpec, Verdict
from .z3_backend import verify_with_z3

JsonDict = dict[str, Any]

CLAIM_SCOPE = (
    "formal equivalence evidence for the accepted projection "
    "and formal mutant refutation within supported semantics"
)

FORBIDDEN_EXTERNAL_FRAGMENT = "benchmarks/v0.12/external_validation/cohort_freeze/cases/"


class ScientificOutcome(StrEnum):
    CERTIFIED_A1 = "CERTIFIED_A1"
    CERTIFIED_A2 = "CERTIFIED_A2"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"


class Capability(StrEnum):
    PURE_SCALAR = "PURE_SCALAR"
    CONTROL_FLOW_SCALAR = "CONTROL_FLOW_SCALAR"
    UNKNOWN = "UNKNOWN"


class Resolution(StrEnum):
    SUPPORTED = "SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class SourceAnalysis:
    resolution: Resolution
    capability: Capability
    reason_code: str
    reason: str
    source_sha256: str
    normalized_source: str
    dedented: bool
    function_name: str | None
    inputs: tuple[tuple[str, str], ...]
    projection: str | None
    mutant_projection: str | None
    mutant_operator: str | None


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_forbidden_external_holdout(
    source_file: Path,
) -> bool:
    normalized = source_file.as_posix().replace("\\", "/").lower()

    forbidden = FORBIDDEN_EXTERNAL_FRAGMENT.lower()

    return forbidden in normalized


def _normalize_source(
    source: str,
) -> tuple[str, ast.Module, bool]:
    try:
        tree = ast.parse(source)
        return source, tree, False
    except SyntaxError:
        dedented = textwrap.dedent(source)
        tree = ast.parse(dedented)
        return dedented, tree, True


def _annotation_name(
    node: ast.expr | None,
) -> str | None:
    if isinstance(node, ast.Name):
        if node.id in {"int", "bool"}:
            return node.id

    return None


def _function_inputs(
    function: ast.FunctionDef,
) -> tuple[
    tuple[tuple[str, str], ...] | None,
    str | None,
]:
    arguments = function.args

    if arguments.posonlyargs:
        return (
            None,
            "positional_only_arguments",
        )

    if arguments.vararg is not None:
        return (
            None,
            "variadic_arguments",
        )

    if arguments.kwarg is not None:
        return (
            None,
            "variadic_keyword_arguments",
        )

    if arguments.kwonlyargs:
        return (
            None,
            "keyword_only_arguments",
        )

    if arguments.defaults:
        return (
            None,
            "default_arguments",
        )

    specs: list[tuple[str, str]] = []

    for argument in arguments.args:
        if argument.arg in {
            "self",
            "cls",
        }:
            return (
                None,
                "bound_instance_or_class_method",
            )

        type_name = _annotation_name(argument.annotation)

        if type_name is None:
            return (
                None,
                ("missing_or_unsupported_annotation:" + argument.arg),
            )

        specs.append(
            (
                argument.arg,
                type_name,
            )
        )

    if not specs:
        return (
            None,
            "zero_argument_function",
        )

    return (
        tuple(specs),
        None,
    )


_ALLOWED_BINOPS = (
    ast.Add,
    ast.Sub,
    ast.Mult,
)

_ALLOWED_UNARY = (
    ast.Not,
    ast.USub,
    ast.UAdd,
)

_ALLOWED_BOOL = (
    ast.And,
    ast.Or,
)

_ALLOWED_COMPARE = (
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)


def _validate_expression(
    expression: ast.expr,
    parameter_names: set[str],
) -> tuple[bool, str]:
    for node in ast.walk(expression):
        if isinstance(
            node,
            (
                ast.Call,
                ast.Attribute,
                ast.Subscript,
                ast.Lambda,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
                ast.List,
                ast.Set,
                ast.Dict,
                ast.Tuple,
                ast.Await,
                ast.Yield,
                ast.YieldFrom,
            ),
        ):
            return (
                False,
                ("unsupported_expression_node:" + type(node).__name__),
            )

        if isinstance(
            node,
            ast.BinOp,
        ) and not isinstance(
            node.op,
            _ALLOWED_BINOPS,
        ):
            return (
                False,
                ("unsupported_binary_operator:" + type(node.op).__name__),
            )

        if isinstance(
            node,
            ast.UnaryOp,
        ) and not isinstance(
            node.op,
            _ALLOWED_UNARY,
        ):
            return (
                False,
                ("unsupported_unary_operator:" + type(node.op).__name__),
            )

        if isinstance(
            node,
            ast.BoolOp,
        ) and not isinstance(
            node.op,
            _ALLOWED_BOOL,
        ):
            return (
                False,
                ("unsupported_boolean_operator:" + type(node.op).__name__),
            )

        if isinstance(
            node,
            ast.Compare,
        ):
            if not all(
                isinstance(
                    operator,
                    _ALLOWED_COMPARE,
                )
                for operator in node.ops
            ):
                return (
                    False,
                    "unsupported_comparison_operator",
                )

        if isinstance(
            node,
            ast.Name,
        ):
            if (
                isinstance(
                    node.ctx,
                    ast.Load,
                )
                and node.id not in parameter_names
            ):
                return (
                    False,
                    ("external_or_unbound_name:" + node.id),
                )

        if isinstance(
            node,
            ast.Constant,
        ):
            if not isinstance(
                node.value,
                (
                    int,
                    bool,
                ),
            ):
                return (
                    False,
                    ("unsupported_constant:" + type(node.value).__name__),
                )

    return (
        True,
        "supported",
    )


class _ProjectionUnsupported(RuntimeError):
    pass


class _NameSubstituter(ast.NodeTransformer):
    def __init__(
        self,
        environment: dict[str, ast.expr],
    ) -> None:
        self._environment = environment

    def visit_Name(
        self,
        node: ast.Name,
    ) -> ast.AST:
        if (
            isinstance(
                node.ctx,
                ast.Load,
            )
            and node.id in self._environment
        ):
            return ast.copy_location(
                copy.deepcopy(self._environment[node.id]),
                node,
            )

        return node


def _substitute_expression(
    expression: ast.expr,
    environment: dict[str, ast.expr],
) -> ast.expr:
    candidate = copy.deepcopy(expression)

    transformed = _NameSubstituter(environment).visit(candidate)

    if not isinstance(
        transformed,
        ast.expr,
    ):
        raise _ProjectionUnsupported("expression substitution failed")

    ast.fix_missing_locations(transformed)

    return transformed


def _is_docstring_statement(
    statement: ast.stmt,
) -> bool:
    return (
        isinstance(
            statement,
            ast.Expr,
        )
        and isinstance(
            statement.value,
            ast.Constant,
        )
        and isinstance(
            statement.value.value,
            str,
        )
    )


def _project_block(
    statements: list[ast.stmt],
    environment: dict[str, ast.expr],
) -> ast.expr:
    index = 0

    while index < len(statements):
        statement = statements[index]

        if _is_docstring_statement(statement):
            index += 1
            continue

        remaining = statements[index + 1 :]

        if isinstance(
            statement,
            ast.Assign,
        ):
            if len(statement.targets) != 1 or not isinstance(
                statement.targets[0],
                ast.Name,
            ):
                raise _ProjectionUnsupported("only simple local assignments are supported")

            target = statement.targets[0].id

            value = _substitute_expression(
                statement.value,
                environment,
            )

            environment = dict(environment)

            environment[target] = value

            index += 1
            continue

        if isinstance(
            statement,
            ast.AnnAssign,
        ):
            if (
                not isinstance(
                    statement.target,
                    ast.Name,
                )
                or statement.value is None
            ):
                raise _ProjectionUnsupported(
                    "only initialized local annotated assignments are supported"
                )

            target = statement.target.id

            value = _substitute_expression(
                statement.value,
                environment,
            )

            environment = dict(environment)

            environment[target] = value

            index += 1
            continue

        if isinstance(
            statement,
            ast.Return,
        ):
            if statement.value is None:
                raise _ProjectionUnsupported("bare return is unsupported")

            return _substitute_expression(
                statement.value,
                environment,
            )

        if isinstance(
            statement,
            ast.If,
        ):
            condition = _substitute_expression(
                statement.test,
                environment,
            )

            true_expression = _project_block(
                [
                    *statement.body,
                    *remaining,
                ],
                dict(environment),
            )

            false_expression = _project_block(
                [
                    *statement.orelse,
                    *remaining,
                ],
                dict(environment),
            )

            result = ast.IfExp(
                test=condition,
                body=true_expression,
                orelse=false_expression,
            )

            ast.fix_missing_locations(result)

            return result

        raise _ProjectionUnsupported("unsupported_statement:" + type(statement).__name__)

    raise _ProjectionUnsupported("execution_path_without_return")


def _return_expression(
    function: ast.FunctionDef,
) -> tuple[
    ast.expr | None,
    str | None,
]:
    try:
        expression = _project_block(
            list(function.body),
            {},
        )

    except _ProjectionUnsupported as exc:
        return (
            None,
            str(exc),
        )

    return (
        expression,
        None,
    )


class _ProjectionMutator(ast.NodeTransformer):
    def __init__(self) -> None:
        self.mutated = False
        self.operator: str | None = None

    def visit_BinOp(
        self,
        node: ast.BinOp,
    ) -> ast.AST:
        node = cast(ast.BinOp, self.generic_visit(node))

        if self.mutated:
            return node

        if isinstance(
            node.op,
            ast.Add,
        ):
            node.op = ast.Sub()
            self.mutated = True
            self.operator = "ADD_TO_SUB"
            return node

        if isinstance(
            node.op,
            ast.Sub,
        ):
            node.op = ast.Add()
            self.mutated = True
            self.operator = "SUB_TO_ADD"
            return node

        if isinstance(
            node.op,
            ast.Mult,
        ):
            node.op = ast.Add()
            self.mutated = True
            self.operator = "MULT_TO_ADD"
            return node

        return node

    def visit_BoolOp(
        self,
        node: ast.BoolOp,
    ) -> ast.AST:
        node = cast(ast.BoolOp, self.generic_visit(node))

        if self.mutated:
            return node

        if isinstance(
            node.op,
            ast.And,
        ):
            node.op = ast.Or()
            self.mutated = True
            self.operator = "AND_TO_OR"
            return node

        if isinstance(
            node.op,
            ast.Or,
        ):
            node.op = ast.And()
            self.mutated = True
            self.operator = "OR_TO_AND"
            return node

        return node

    def visit_Compare(
        self,
        node: ast.Compare,
    ) -> ast.AST:
        node = cast(ast.Compare, self.generic_visit(node))

        if self.mutated:
            return node

        if len(node.ops) != 1:
            return node

        operator = node.ops[0]

        replacements: list[
            tuple[
                type[ast.cmpop],
                ast.cmpop,
                str,
            ]
        ] = [
            (
                ast.Eq,
                ast.NotEq(),
                "EQ_TO_NE",
            ),
            (
                ast.NotEq,
                ast.Eq(),
                "NE_TO_EQ",
            ),
            (
                ast.Lt,
                ast.GtE(),
                "LT_TO_GE",
            ),
            (
                ast.LtE,
                ast.Gt(),
                "LE_TO_GT",
            ),
            (
                ast.Gt,
                ast.LtE(),
                "GT_TO_LE",
            ),
            (
                ast.GtE,
                ast.Lt(),
                "GE_TO_LT",
            ),
        ]

        for (
            source_type,
            replacement,
            name,
        ) in replacements:
            if isinstance(
                operator,
                source_type,
            ):
                node.ops[0] = replacement
                self.mutated = True
                self.operator = name
                return node

        return node

    def visit_Constant(
        self,
        node: ast.Constant,
    ) -> ast.AST:
        if self.mutated:
            return node

        if isinstance(
            node.value,
            bool,
        ):
            self.mutated = True
            self.operator = "BOOL_CONSTANT_FLIP"
            return ast.copy_location(
                ast.Constant(value=not node.value),
                node,
            )

        if isinstance(
            node.value,
            int,
        ):
            self.mutated = True
            self.operator = "INT_CONSTANT_PLUS_ONE"
            return ast.copy_location(
                ast.Constant(value=node.value + 1),
                node,
            )

        return node


def _mutate_projection(
    expression: ast.expr,
) -> tuple[
    str | None,
    str | None,
]:
    mutant = copy.deepcopy(expression)

    mutator = _ProjectionMutator()

    mutant = mutator.visit(mutant)

    ast.fix_missing_locations(mutant)

    if not mutator.mutated:
        return (
            None,
            None,
        )

    return (
        ast.unparse(mutant),
        mutator.operator,
    )


def analyze_source(
    source_file: Path,
) -> SourceAnalysis:
    if is_forbidden_external_holdout(source_file):
        raise ValueError("V0.13 development access to the frozen external holdout is forbidden")

    raw_source = source_file.read_text(encoding="utf-8")

    raw_sha = _sha256_text(raw_source)

    try:
        (
            normalized_source,
            tree,
            dedented,
        ) = _normalize_source(raw_source)
    except SyntaxError as exc:
        return SourceAnalysis(
            resolution=(Resolution.UNSUPPORTED),
            capability=(Capability.UNKNOWN),
            reason_code="parse_error",
            reason=str(exc),
            source_sha256=raw_sha,
            normalized_source=raw_source,
            dedented=False,
            function_name=None,
            inputs=(),
            projection=None,
            mutant_projection=None,
            mutant_operator=None,
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

    if async_functions:
        return SourceAnalysis(
            resolution=(Resolution.UNSUPPORTED),
            capability=(Capability.UNKNOWN),
            reason_code=("async_function"),
            reason=("initial scalar core does not support async"),
            source_sha256=raw_sha,
            normalized_source=(normalized_source),
            dedented=dedented,
            function_name=None,
            inputs=(),
            projection=None,
            mutant_projection=None,
            mutant_operator=None,
        )

    if len(functions) != 1:
        return SourceAnalysis(
            resolution=(Resolution.AMBIGUOUS),
            capability=(Capability.UNKNOWN),
            reason_code=("function_resolution_ambiguous"),
            reason=("source must contain exactly one top-level function"),
            source_sha256=raw_sha,
            normalized_source=(normalized_source),
            dedented=dedented,
            function_name=None,
            inputs=(),
            projection=None,
            mutant_projection=None,
            mutant_operator=None,
        )

    function = functions[0]

    (
        inputs,
        input_error,
    ) = _function_inputs(function)

    if inputs is None:
        return SourceAnalysis(
            resolution=(Resolution.UNSUPPORTED),
            capability=(Capability.UNKNOWN),
            reason_code=("unsupported_signature"),
            reason=(input_error or "unsupported_signature"),
            source_sha256=raw_sha,
            normalized_source=(normalized_source),
            dedented=dedented,
            function_name=(function.name),
            inputs=(),
            projection=None,
            mutant_projection=None,
            mutant_operator=None,
        )

    (
        expression,
        return_error,
    ) = _return_expression(function)

    if expression is None:
        return SourceAnalysis(
            resolution=(Resolution.UNSUPPORTED),
            capability=(Capability.UNKNOWN),
            reason_code=("unsupported_control_flow"),
            reason=(return_error or "unsupported_control_flow"),
            source_sha256=raw_sha,
            normalized_source=(normalized_source),
            dedented=dedented,
            function_name=(function.name),
            inputs=inputs,
            projection=None,
            mutant_projection=None,
            mutant_operator=None,
        )

    parameter_names = {
        name
        for (
            name,
            _type_name,
        ) in inputs
    }

    (
        expression_supported,
        expression_reason,
    ) = _validate_expression(
        expression,
        parameter_names,
    )

    if not expression_supported:
        return SourceAnalysis(
            resolution=(Resolution.UNSUPPORTED),
            capability=(Capability.UNKNOWN),
            reason_code=("unsupported_expression"),
            reason=expression_reason,
            source_sha256=raw_sha,
            normalized_source=(normalized_source),
            dedented=dedented,
            function_name=(function.name),
            inputs=inputs,
            projection=None,
            mutant_projection=None,
            mutant_operator=None,
        )

    has_control_flow = any(
        isinstance(
            node,
            (
                ast.Assign,
                ast.AnnAssign,
                ast.If,
                ast.IfExp,
            ),
        )
        for node in ast.walk(function)
    )

    capability = Capability.CONTROL_FLOW_SCALAR if has_control_flow else Capability.PURE_SCALAR

    projection = ast.unparse(expression)

    (
        mutant_projection,
        mutant_operator,
    ) = _mutate_projection(expression)

    return SourceAnalysis(
        resolution=Resolution.SUPPORTED,
        capability=capability,
        reason_code="supported",
        reason=("accepted by generic scalar normalization frontend"),
        source_sha256=raw_sha,
        normalized_source=(normalized_source),
        dedented=dedented,
        function_name=function.name,
        inputs=inputs,
        projection=projection,
        mutant_projection=(mutant_projection),
        mutant_operator=(mutant_operator),
    )


def _evidence_to_json(
    evidence: Any,
) -> JsonDict:
    return {
        "verdict": evidence.verdict.value,
        "contract_id": evidence.contract_id,
        "backend": evidence.backend,
        "counterexample": evidence.counterexample,
        "observed_result": evidence.observed_result,
        "postcondition_satisfied": (evidence.postcondition_satisfied),
        "replay_validated": evidence.replay_validated,
        "reason_code": evidence.reason_code,
        "reason": evidence.reason,
        "metadata": evidence.metadata,
    }


def _base_result(
    *,
    case_id: str,
    source_file: Path,
    analysis: SourceAnalysis,
) -> JsonDict:
    return {
        "schema_version": ("BIZPROOF-V0.13-UNIVERSAL-CERTIFIER-1"),
        "case_id": case_id,
        "source_file": source_file.as_posix(),
        "source_sha256": analysis.source_sha256,
        "function_name": analysis.function_name,
        "resolution": analysis.resolution.value,
        "capability": analysis.capability.value,
        "reason_code": analysis.reason_code,
        "reason": analysis.reason,
        "dedented": analysis.dedented,
        "inputs": [
            {
                "name": name,
                "type": type_name,
            }
            for (
                name,
                type_name,
            ) in analysis.inputs
        ],
        "projection": analysis.projection,
        "mutant_projection": (analysis.mutant_projection),
        "mutant_operator": analysis.mutant_operator,
        "claim_scope": CLAIM_SCOPE,
        "full_arbitrary_source_equivalence": False,
    }


def certify_source(
    *,
    source_file: Path,
    case_id: str,
) -> JsonDict:
    analysis = analyze_source(source_file)

    result = _base_result(
        case_id=case_id,
        source_file=source_file,
        analysis=analysis,
    )

    if analysis.resolution is Resolution.AMBIGUOUS:
        result.update(
            {
                "scientific_outcome": (ScientificOutcome.AMBIGUOUS.value),
                "certified": False,
                "a_level": None,
                "formal": None,
                "mutant": None,
            }
        )

        return result

    if analysis.resolution is not Resolution.SUPPORTED:
        result.update(
            {
                "scientific_outcome": (ScientificOutcome.UNSUPPORTED.value),
                "certified": False,
                "a_level": None,
                "formal": None,
                "mutant": None,
            }
        )

        return result

    assert analysis.function_name is not None

    assert analysis.projection is not None

    input_specs = tuple(
        InputSpec(
            name=name,
            type_name=type_name,
            minimum=None,
            maximum=None,
            label=None,
        )
        for (
            name,
            type_name,
        ) in analysis.inputs
    )

    with tempfile.TemporaryDirectory(prefix="bizproof-v013-") as tmp:
        normalized_file = Path(tmp) / "candidate.py"

        normalized_file.write_text(
            analysis.normalized_source,
            encoding="utf-8",
        )

        correct_contract = BusinessContract(
            contract_id=(case_id + "::projection"),
            title=("V0.13 generic source-to-projection proof"),
            target=TargetSpec(
                source=normalized_file,
                function=(analysis.function_name),
            ),
            inputs=input_specs,
            precondition="True",
            postcondition=("result == (" + analysis.projection + ")"),
            expected_outcome=("source semantics equal accepted projection"),
        )

        correct_evidence = verify_with_z3(correct_contract)

        correct_json = _evidence_to_json(correct_evidence)

        mutant_json: JsonDict | None = None

        mutant_refuted = False

        if analysis.mutant_projection is not None:
            mutant_contract = BusinessContract(
                contract_id=(case_id + "::mutant"),
                title=("V0.13 generic prospective mutant"),
                target=TargetSpec(
                    source=(normalized_file),
                    function=(analysis.function_name),
                ),
                inputs=input_specs,
                precondition="True",
                postcondition=("result == (" + analysis.mutant_projection + ")"),
                expected_outcome=("prospective mutant must be refuted"),
            )

            mutant_evidence = verify_with_z3(mutant_contract)

            mutant_json = _evidence_to_json(mutant_evidence)

            mutant_refuted = (
                mutant_evidence.verdict is Verdict.DISPROVED
                and mutant_evidence.replay_validated is True
            )

        if correct_evidence.verdict is Verdict.PROVED:
            if mutant_refuted:
                outcome = ScientificOutcome.CERTIFIED_A2

                a_level = "A2"

            else:
                outcome = ScientificOutcome.CERTIFIED_A1

                a_level = "A1"

            result.update(
                {
                    "scientific_outcome": outcome.value,
                    "certified": True,
                    "a_level": a_level,
                    "formal": correct_json,
                    "mutant": mutant_json,
                    "mutant_refuted": mutant_refuted,
                }
            )

            return result

        if correct_evidence.verdict is Verdict.UNKNOWN:
            result.update(
                {
                    "scientific_outcome": (ScientificOutcome.UNSUPPORTED.value),
                    "certified": False,
                    "a_level": None,
                    "reason_code": ("formal_backend_unknown"),
                    "reason": (correct_evidence.reason),
                    "formal": correct_json,
                    "mutant": mutant_json,
                }
            )

            return result

        result.update(
            {
                "scientific_outcome": (ScientificOutcome.AMBIGUOUS.value),
                "certified": False,
                "a_level": None,
                "reason_code": ("projection_not_preserved"),
                "reason": ("accepted projection was contradicted by formal verification"),
                "formal": correct_json,
                "mutant": mutant_json,
            }
        )

        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=("BIZPROOF V0.13 generic source-level certifier"))

    parser.add_argument(
        "--source-file",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--case-id",
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    result = certify_source(
        source_file=args.source_file,
        case_id=args.case_id,
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "case_id=",
        result["case_id"],
    )

    print(
        "capability=",
        result["capability"],
    )

    print(
        "outcome=",
        result["scientific_outcome"],
    )

    print(
        "certified=",
        result["certified"],
    )

    print(
        "a_level=",
        result["a_level"],
    )


if __name__ == "__main__":
    main()
