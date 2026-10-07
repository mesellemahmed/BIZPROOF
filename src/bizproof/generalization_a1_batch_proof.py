from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import textwrap
from pathlib import Path
from typing import Any, TypeAlias

import z3

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_CANDIDATES = 11

EXPECTED_PHASE_Q_A2 = 1

EXPECTED_OPENFISCA_COMMIT = "ebcb7782d17058495c6ca33c278e373e167b641b"

ALLOWED_SEMANTIC_ABSTRACTIONS = {
    "D": "SC-D-DECIMAL-001",
    "not_": "SC-NP-NOT-001",
    "min_": "SC-NP-MIN-001",
    "where": "SC-NP-WHERE-001",
    "nb_enf": "SC-NB-ENF-001",
}


class ProofUnsupported(ValueError):
    pass


class _Opaque:
    pass


def _load_json(
    path: Path,
) -> JsonDict:

    value = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(f"expected JSON object: {path}")

    return value


def _load_jsonl(
    path: Path,
) -> list[JsonDict]:

    result: list[JsonDict] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue

        value = json.loads(raw)

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(f"expected JSON object: {path}")

        result.append(value)

    return result


def _sha256_text(
    value: str,
) -> str:

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(
    path: Path,
) -> str:

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(
    value: JsonDict,
) -> str:

    text = json.dumps(
        value,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=True,
    )

    return _sha256_text(text)


def _canonical_expression(
    value: str,
) -> str:

    node = ast.parse(
        value,
        mode="eval",
    ).body

    return ast.unparse(node)


def _numeric_bool(
    condition: Any,
) -> Any:

    return z3.If(
        condition,
        z3.RealVal(1),
        z3.RealVal(0),
    )


def _truth(
    value: Any,
) -> Any:

    return value != z3.RealVal(0)


def _constant(
    value: object,
) -> Any:

    if isinstance(
        value,
        bool,
    ):
        return z3.RealVal(1 if value else 0)

    if isinstance(
        value,
        int,
    ):
        return z3.RealVal(value)

    if isinstance(
        value,
        float,
    ):
        return z3.RealVal(str(value))

    raise ProofUnsupported(f"unsupported symbolic constant: {value!r}")


class SourceCompiler:
    def __init__(
        self,
        binding_variables: dict[
            str,
            Any,
        ],
    ) -> None:

        self.binding_variables = binding_variables

        self.environment: dict[
            str,
            Any,
        ] = {}

        self.used_bindings: set[str] = set()

    def expression(
        self,
        node: ast.expr,
    ) -> Any:

        if isinstance(
            node,
            ast.Constant,
        ):
            return _constant(node.value)

        if isinstance(
            node,
            ast.Name,
        ):
            if node.id not in self.environment:
                raise ProofUnsupported("unbound source name: " + node.id)

            value = self.environment[node.id]

            if isinstance(
                value,
                _Opaque,
            ):
                raise ProofUnsupported("opaque value used directly: " + node.id)

            return value

        if isinstance(
            node,
            ast.Call,
        ):
            expression = _canonical_expression(ast.unparse(node))

            if expression in self.binding_variables:
                self.used_bindings.add(expression)

                return self.binding_variables[expression]

            if (
                isinstance(
                    node.func,
                    ast.Name,
                )
                and node.func.id == "not_"
                and len(node.args) == 1
            ):
                return _numeric_bool(z3.Not(_truth(self.expression(node.args[0]))))

            if (
                isinstance(
                    node.func,
                    ast.Name,
                )
                and node.func.id == "min_"
                and len(node.args) == 2
            ):
                left = self.expression(node.args[0])

                right = self.expression(node.args[1])

                return z3.If(
                    left <= right,
                    left,
                    right,
                )

            if (
                isinstance(
                    node.func,
                    ast.Name,
                )
                and node.func.id == "where"
                and len(node.args) == 3
            ):
                condition = self.expression(node.args[0])

                when_true = self.expression(node.args[1])

                when_false = self.expression(node.args[2])

                return z3.If(
                    _truth(condition),
                    when_true,
                    when_false,
                )

            if (
                isinstance(
                    node.func,
                    ast.Name,
                )
                and node.func.id == "D"
                and len(node.args) == 1
                and isinstance(
                    node.args[0],
                    ast.Constant,
                )
                and isinstance(
                    node.args[0].value,
                    str,
                )
            ):
                return z3.RealVal(node.args[0].value)

            raise ProofUnsupported("unsupported source call: " + expression)

        if isinstance(
            node,
            ast.BinOp,
        ):
            left = self.expression(node.left)

            right = self.expression(node.right)

            if isinstance(
                node.op,
                ast.Add,
            ):
                return left + right

            if isinstance(
                node.op,
                ast.Sub,
            ):
                return left - right

            if isinstance(
                node.op,
                ast.Mult,
            ):
                return left * right

            if isinstance(
                node.op,
                ast.Div,
            ):
                return left / right

            raise ProofUnsupported("unsupported source BinOp: " + type(node.op).__name__)

        if isinstance(
            node,
            ast.UnaryOp,
        ):
            value = self.expression(node.operand)

            if isinstance(
                node.op,
                ast.USub,
            ):
                return -value

            if isinstance(
                node.op,
                ast.UAdd,
            ):
                return value

            if isinstance(
                node.op,
                ast.Not,
            ):
                return _numeric_bool(z3.Not(_truth(value)))

            raise ProofUnsupported("unsupported source UnaryOp")

        if isinstance(
            node,
            ast.Compare,
        ):
            left = self.expression(node.left)

            conditions: list[Any] = []

            for (
                operator,
                comparator,
            ) in zip(
                node.ops,
                node.comparators,
                strict=True,
            ):
                right = self.expression(comparator)

                if isinstance(
                    operator,
                    ast.Eq,
                ):
                    condition = left == right

                elif isinstance(
                    operator,
                    ast.NotEq,
                ):
                    condition = left != right

                elif isinstance(
                    operator,
                    ast.Lt,
                ):
                    condition = left < right

                elif isinstance(
                    operator,
                    ast.LtE,
                ):
                    condition = left <= right

                elif isinstance(
                    operator,
                    ast.Gt,
                ):
                    condition = left > right

                elif isinstance(
                    operator,
                    ast.GtE,
                ):
                    condition = left >= right

                else:
                    raise ProofUnsupported("unsupported source comparison")

                conditions.append(condition)

                left = right

            return _numeric_bool(z3.And(*conditions))

        if isinstance(
            node,
            ast.BoolOp,
        ):
            values = [_truth(self.expression(item)) for item in node.values]

            if isinstance(
                node.op,
                ast.And,
            ):
                return _numeric_bool(z3.And(*values))

            if isinstance(
                node.op,
                ast.Or,
            ):
                return _numeric_bool(z3.Or(*values))

            raise ProofUnsupported("unsupported source BoolOp")

        if isinstance(
            node,
            ast.IfExp,
        ):
            return z3.If(
                _truth(self.expression(node.test)),
                self.expression(node.body),
                self.expression(node.orelse),
            )

        raise ProofUnsupported("unsupported source expression: " + type(node).__name__)

    def function(
        self,
        source: str,
    ) -> Any:

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
            raise ProofUnsupported("source slice does not contain exactly one function")

        function = functions[0]

        for statement in function.body:
            if (
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
            ):
                continue

            if isinstance(
                statement,
                ast.Assign,
            ):
                if len(statement.targets) != 1 or not isinstance(
                    statement.targets[0],
                    ast.Name,
                ):
                    raise ProofUnsupported("unsupported assignment target")

                target = statement.targets[0].id

                try:
                    self.environment[target] = self.expression(statement.value)

                except ProofUnsupported:
                    self.environment[target] = _Opaque()

                continue

            if isinstance(
                statement,
                ast.AnnAssign,
            ):
                if not isinstance(
                    statement.target,
                    ast.Name,
                ):
                    raise ProofUnsupported("unsupported annotated target")

                if statement.value is None:
                    self.environment[statement.target.id] = _Opaque()

                else:
                    try:
                        self.environment[statement.target.id] = self.expression(statement.value)

                    except ProofUnsupported:
                        self.environment[statement.target.id] = _Opaque()

                continue

            if isinstance(
                statement,
                ast.AugAssign,
            ):
                if not isinstance(
                    statement.target,
                    ast.Name,
                ):
                    raise ProofUnsupported("unsupported augmented target")

                name = statement.target.id

                if name not in self.environment:
                    raise ProofUnsupported("unbound augmented target")

                current = self.environment[name]

                if isinstance(
                    current,
                    _Opaque,
                ):
                    raise ProofUnsupported("opaque augmented target")

                value = self.expression(statement.value)

                if isinstance(
                    statement.op,
                    ast.Add,
                ):
                    self.environment[name] = current + value

                elif isinstance(
                    statement.op,
                    ast.Sub,
                ):
                    self.environment[name] = current - value

                else:
                    raise ProofUnsupported("unsupported augmented operation")

                continue

            if isinstance(
                statement,
                ast.Return,
            ):
                if statement.value is None:
                    raise ProofUnsupported("None return unsupported")

                return self.expression(statement.value)

            raise ProofUnsupported("unsupported source statement: " + type(statement).__name__)

        raise ProofUnsupported("source function has no supported return")


def _comparison(
    operator: str,
    left: Any,
    right: Any,
) -> Any:

    if operator in {
        "eq",
        "==",
    }:
        return left == right

    if operator in {
        "ne",
        "!=",
    }:
        return left != right

    if operator in {
        "lt",
        "<",
    }:
        return left < right

    if operator in {
        "le",
        "<=",
    }:
        return left <= right

    if operator in {
        "gt",
        ">",
    }:
        return left > right

    if operator in {
        "ge",
        ">=",
    }:
        return left >= right

    raise ProofUnsupported("unsupported BSIR comparison: " + operator)


def _compile_ir(
    node: object,
    binding_by_id: dict[
        str,
        Any,
    ],
) -> Any:

    if not isinstance(
        node,
        dict,
    ):
        return _constant(node)

    op = str(node.get("op"))

    if op == "binding":
        binding_id = str(node["binding_id"])

        if binding_id not in binding_by_id:
            raise ProofUnsupported("BSIR binding missing: " + binding_id)

        return binding_by_id[binding_id]

    if op in {
        "const",
        "constant",
    }:
        return _constant(node["value"])

    if op == "add":
        return _compile_ir(
            node["left"],
            binding_by_id,
        ) + _compile_ir(
            node["right"],
            binding_by_id,
        )

    if op == "sub":
        return _compile_ir(
            node["left"],
            binding_by_id,
        ) - _compile_ir(
            node["right"],
            binding_by_id,
        )

    if op == "mul":
        return _compile_ir(
            node["left"],
            binding_by_id,
        ) * _compile_ir(
            node["right"],
            binding_by_id,
        )

    if op == "div":
        return _compile_ir(
            node["left"],
            binding_by_id,
        ) / _compile_ir(
            node["right"],
            binding_by_id,
        )

    if op == "neg":
        return -_compile_ir(
            node["value"],
            binding_by_id,
        )

    if op == "pos":
        return _compile_ir(
            node["value"],
            binding_by_id,
        )

    if op == "compare":
        left = _compile_ir(
            node["left"],
            binding_by_id,
        )

        comparators = node.get(
            "comparators",
            [],
        )

        operators = node.get(
            "operators",
            [],
        )

        if not isinstance(
            comparators,
            list,
        ):
            raise ProofUnsupported("invalid BSIR comparators")

        if not isinstance(
            operators,
            list,
        ):
            raise ProofUnsupported("invalid BSIR operators")

        if len(comparators) != len(operators):
            raise ProofUnsupported("BSIR comparison arity mismatch")

        conditions: list[Any] = []

        for (
            operator,
            comparator,
        ) in zip(
            operators,
            comparators,
            strict=True,
        ):
            right = _compile_ir(
                comparator,
                binding_by_id,
            )

            conditions.append(
                _comparison(
                    str(operator),
                    left,
                    right,
                )
            )

            left = right

        return _numeric_bool(z3.And(*conditions))

    if op in {
        "and",
        "bool_and",
    }:
        raw_values = node.get("values")

        if not isinstance(
            raw_values,
            list,
        ):
            raw_values = [
                node["left"],
                node["right"],
            ]

        return _numeric_bool(
            z3.And(
                *[
                    _truth(
                        _compile_ir(
                            value,
                            binding_by_id,
                        )
                    )
                    for value in raw_values
                ]
            )
        )

    if op in {
        "or",
        "bool_or",
    }:
        raw_values = node.get("values")

        if not isinstance(
            raw_values,
            list,
        ):
            raw_values = [
                node["left"],
                node["right"],
            ]

        return _numeric_bool(
            z3.Or(
                *[
                    _truth(
                        _compile_ir(
                            value,
                            binding_by_id,
                        )
                    )
                    for value in raw_values
                ]
            )
        )

    if op == "not":
        return _numeric_bool(
            z3.Not(
                _truth(
                    _compile_ir(
                        node["value"],
                        binding_by_id,
                    )
                )
            )
        )

    if op in {
        "if",
        "ite",
    }:
        condition_node = node.get("condition") or node.get("test")

        then_node = node.get("then") or node.get("body")

        else_node = node.get("else") or node.get("orelse")

        return z3.If(
            _truth(
                _compile_ir(
                    condition_node,
                    binding_by_id,
                )
            ),
            _compile_ir(
                then_node,
                binding_by_id,
            ),
            _compile_ir(
                else_node,
                binding_by_id,
            ),
        )

    if op == "min":
        left = _compile_ir(
            node["left"],
            binding_by_id,
        )

        right = _compile_ir(
            node["right"],
            binding_by_id,
        )

        return z3.If(
            left <= right,
            left,
            right,
        )

    if op == "max":
        left = _compile_ir(
            node["left"],
            binding_by_id,
        )

        right = _compile_ir(
            node["right"],
            binding_by_id,
        )

        return z3.If(
            left >= right,
            left,
            right,
        )

    raise ProofUnsupported("unsupported BSIR op: " + op)


def _mutate_ir(
    node: object,
) -> tuple[
    object,
    str,
]:

    if not isinstance(
        node,
        dict,
    ):
        return (
            {
                "op": "add",
                "left": copy.deepcopy(node),
                "right": {
                    "op": "const",
                    "value": 1,
                },
            },
            "constant-plus-one",
        )

    op = str(node.get("op"))

    result = copy.deepcopy(node)

    if op == "binding":
        return (
            {
                "op": "add",
                "left": result,
                "right": {
                    "op": "const",
                    "value": 1,
                },
            },
            "binding-plus-one",
        )

    if op == "add":
        result["op"] = "sub"

        return (
            result,
            "add-to-sub",
        )

    if op == "sub":
        result["op"] = "add"

        return (
            result,
            "sub-to-add",
        )

    if op == "mul":
        result["op"] = "add"

        return (
            result,
            "mul-to-add",
        )

    if op == "neg":
        return (
            result["value"],
            "remove-negation",
        )

    if op == "compare":
        operators = list(
            result.get(
                "operators",
                [],
            )
        )

        if operators:
            replacement = {
                "le": "lt",
                "lt": "le",
                "ge": "gt",
                "gt": "ge",
                "eq": "ne",
                "ne": "eq",
            }

            current = str(operators[0])

            operators[0] = replacement.get(
                current,
                "ne",
            )

            result["operators"] = operators

            return (
                result,
                "comparison-operator-change",
            )

    for key in (
        "left",
        "right",
        "value",
    ):
        if key in result:
            mutated, description = _mutate_ir(result[key])

            result[key] = mutated

            return (
                result,
                description,
            )

    return (
        {
            "op": "add",
            "left": result,
            "right": {
                "op": "const",
                "value": 1,
            },
        },
        "fallback-plus-one",
    )


def _validated_semantic_contracts(
    repo_root: Path,
) -> dict[str, str]:

    result: dict[
        str,
        str,
    ] = {}

    decimal = _load_json(repo_root / ("benchmarks/v0.11/semantic_contracts/decimal_contract.json"))

    if decimal.get("semantic_contract_status") == "VALIDATED":
        result["D"] = str(decimal["contract_id"])

    aliases = _load_json(
        repo_root / ("benchmarks/v0.11/semantic_contract_closure/numpy_alias_contracts.json")
    )

    raw_aliases = aliases.get(
        "contracts",
        [],
    )

    if isinstance(
        raw_aliases,
        list,
    ):
        for item in raw_aliases:
            if not isinstance(
                item,
                dict,
            ):
                continue

            if str(item.get("semantic_contract_status")).startswith("VALIDATED"):
                result[str(item["primitive"])] = str(item["contract_id"])

    nb_enf = _load_json(
        repo_root / ("benchmarks/v0.11/semantic_contract_closure/nb_enf_contract.json")
    )

    if str(nb_enf.get("semantic_contract_status")).startswith("VALIDATED"):
        result["nb_enf"] = str(nb_enf["contract_id"])

    return result


def _protocol_a1(
    path: Path,
) -> JsonDict:

    lines = path.read_text(encoding="utf-8").splitlines()

    matches = [
        {
            "line": index + 1,
            "text": line,
        }
        for (
            index,
            line,
        ) in enumerate(lines)
        if ("`CERTIFIED_A1`" in line and ("declarative source-to-BVC bindings only") in line)
    ]

    if len(matches) != 1:
        raise ValueError("CERTIFIED_A1 protocol definition not unique")

    return matches[0]


def _sample_assignments(
    names: list[str],
) -> list[
    dict[
        str,
        int,
    ]
]:

    values: list[
        dict[
            str,
            int,
        ]
    ] = []

    values.append({name: 0 for name in names})

    values.append({name: 1 for name in names})

    values.append({name: -1 for name in names})

    values.append(
        {
            name: (index - 2)
            for (
                index,
                name,
            ) in enumerate(names)
        }
    )

    for selected in names[:8]:
        values.append({name: (2 if name == selected else 0) for name in names})

    return values


def _replay_equivalence(
    left: Any,
    right: Any,
    variables: dict[
        str,
        Any,
    ],
) -> int:

    assignments = _sample_assignments(sorted(variables))

    for assignment in assignments:
        substitutions = [
            (
                variables[name],
                z3.RealVal(value),
            )
            for (
                name,
                value,
            ) in assignment.items()
        ]

        check = z3.simplify(
            z3.substitute(
                left,
                *substitutions,
            )
            == z3.substitute(
                right,
                *substitutions,
            )
        )

        if not z3.is_true(check):
            raise ValueError(
                "concrete replay mismatch: "
                + json.dumps(
                    assignment,
                    sort_keys=True,
                )
            )

    return len(assignments)


def _model_witness(
    model: Any,
    variables: dict[
        str,
        Any,
    ],
) -> JsonDict:

    result: JsonDict = {}

    for name in sorted(variables):
        result[name] = str(
            model.eval(
                variables[name],
                model_completion=True,
            )
        )

    return result


def _proof_candidate(
    *,
    candidate_id: str,
    source_record: JsonDict,
    manifest: JsonDict,
    probe: JsonDict,
    validated_contracts: dict[
        str,
        str,
    ],
) -> JsonDict:

    result: JsonDict = {
        "candidate_id": candidate_id,
        "source": source_record["source_id"],
        "class": source_record["class"],
        "function": source_record["function"],
        "status": "PROOF_REVIEW_REQUIRED",
        "terminal_outcome": None,
        "certification_claim": False,
    }

    try:
        if source_record["resolved_commit"] != EXPECTED_OPENFISCA_COMMIT:
            raise ProofUnsupported("locked commit mismatch")

        source_slice = str(source_record["source_slice"])

        if _sha256_text(source_slice) != source_record["function_sha256"]:
            raise ProofUnsupported("function SHA mismatch")

        structural_bindings = manifest["bindings"]

        if not isinstance(
            structural_bindings,
            list,
        ):
            raise ProofUnsupported("invalid structural bindings")

        structural_expressions = {
            _canonical_expression(str(item["source_expression"])): item
            for item in structural_bindings
        }

        required = probe.get(
            "required_bindings",
            [],
        )

        if not isinstance(
            required,
            list,
        ):
            raise ProofUnsupported("invalid probe required bindings")

        variable_by_expression: dict[
            str,
            Any,
        ] = {}

        variable_by_binding_id: dict[
            str,
            Any,
        ] = {}

        variable_by_name: dict[
            str,
            Any,
        ] = {}

        semantic_contracts_used: dict[
            str,
            str,
        ] = {}

        structural_seen: set[str] = set()

        for (
            index,
            item,
        ) in enumerate(required):
            if not isinstance(
                item,
                dict,
            ):
                raise ProofUnsupported("invalid required binding item")

            expression = _canonical_expression(str(item["source_expression"]))

            primitive = str(item["primitive"])

            binding_id = str(item["binding_id"])

            variable_name = f"b_{candidate_id[:6]}_{index}"

            variable = z3.Real(variable_name)

            variable_by_expression[expression] = variable

            variable_by_binding_id[binding_id] = variable

            variable_by_name[variable_name] = variable

            if expression in structural_expressions:
                structural_seen.add(expression)

                continue

            if primitive not in validated_contracts:
                raise ProofUnsupported(
                    "required non-structural binding "
                    "has no validated semantic contract: "
                    f"{primitive} / {expression}"
                )

            semantic_contracts_used[primitive] = validated_contracts[primitive]

        missing_structural = set(structural_expressions) - structural_seen

        if missing_structural:
            raise ProofUnsupported(
                "Phase-R bindings absent from symbolic probe: " + repr(sorted(missing_structural))
            )

        input_references = probe.get(
            "input_references",
            [],
        )

        if input_references:
            raise ProofUnsupported("direct input references require separate A1 handling")

        compiler = SourceCompiler(variable_by_expression)

        source_expression = compiler.function(source_slice)

        ir = probe.get("ir")

        if not isinstance(
            ir,
            dict,
        ):
            raise ProofUnsupported("probe IR missing")

        if ir.get("ir_version") != "BSIR-SKELETON-0.11":
            raise ProofUnsupported("unexpected BSIR version")

        if "return" not in ir:
            raise ProofUnsupported("BSIR return missing")

        ir_expression = _compile_ir(
            ir["return"],
            variable_by_binding_id,
        )

        correct_solver = z3.Solver()

        correct_solver.add(source_expression != ir_expression)

        correct_status = correct_solver.check()

        if correct_status != z3.unsat:
            raise ProofUnsupported(f"source/BSIR equivalence not proved: {correct_status}")

        replay_cases = _replay_equivalence(
            source_expression,
            ir_expression,
            variable_by_name,
        )

        (
            mutant_ir,
            mutation,
        ) = _mutate_ir(ir["return"])

        mutant_expression = _compile_ir(
            mutant_ir,
            variable_by_binding_id,
        )

        mutant_solver = z3.Solver()

        mutant_solver.add(source_expression != mutant_expression)

        mutant_status = mutant_solver.check()

        if mutant_status != z3.sat:
            raise ProofUnsupported(f"mutant was not distinguishable: {mutant_status}")

        mutant_model = mutant_solver.model()

        witness = _model_witness(
            mutant_model,
            variable_by_name,
        )

        source_at_witness = str(
            mutant_model.eval(
                source_expression,
                model_completion=True,
            )
        )

        mutant_at_witness = str(
            mutant_model.eval(
                mutant_expression,
                model_completion=True,
            )
        )

        if source_at_witness == mutant_at_witness:
            raise ProofUnsupported("mutant witness failed replay")

        expected_structural = {
            _canonical_expression(str(item["source_expression"])) for item in structural_bindings
        }

        if compiler.used_bindings != set(variable_by_expression):
            missing_in_source = set(variable_by_expression) - compiler.used_bindings

            if missing_in_source:
                raise ProofUnsupported(
                    "probe binding not observed "
                    "during independent source compile: " + repr(sorted(missing_in_source))
                )

        result.update(
            {
                "status": "PROVED_A1_SOURCE_TO_BSIR",
                "terminal_outcome": "CERTIFIED_A1",
                "structural_binding_count": len(structural_bindings),
                "structural_binding_expressions": sorted(expected_structural),
                "semantic_contract_abstractions": semantic_contracts_used,
                "probe_binding_count": len(required),
                "source_function_sha256": source_record["function_sha256"],
                "source_file_sha256": source_record["source_file_sha256"],
                "binding_manifest_sha256": manifest["binding_manifest_sha256"],
                "probe_ir_sha256": probe["ir_sha256"],
                "solver": {
                    "correct": str(correct_status),
                    "mutant": str(mutant_status),
                },
                "replay_cases": replay_cases,
                "mutation": mutation,
                "mutant_witness": witness,
                "source_at_mutant_witness": source_at_witness,
                "mutant_at_witness": mutant_at_witness,
                "proof_obligations": {
                    "locked_source": True,
                    "frozen_function_sha": True,
                    "declarative_bindings_closed": True,
                    "semantic_contracts_validated": True,
                    "independent_source_ast_compile": True,
                    "bsir_compile": True,
                    "symbolic_equivalence_unsat": True,
                    "concrete_replay": True,
                    "mutant_detected_sat": True,
                    "mutant_witness_replayed": True,
                },
                "certification_claim": True,
            }
        )

    except (
        ProofUnsupported,
        ValueError,
        KeyError,
        TypeError,
        z3.Z3Exception,
    ) as exc:
        result["review_reason"] = str(exc)

    digest_payload = dict(result)

    result["proof_digest"] = _canonical_digest(digest_payload)

    return result


def build_batch(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    phase_r_root = repo_root / ("benchmarks/v0.11/declarative_binding_closure")

    worklist = _load_jsonl(phase_r_root / "a1_proof_worklist.jsonl")

    manifests = _load_jsonl(phase_r_root / "binding_manifests.jsonl")

    sources = _load_jsonl(phase_r_root / "source_slices.jsonl")

    probes = _load_jsonl(repo_root / ("benchmarks/v0.11/symbolic_probe/probe.jsonl"))

    checkout = _load_json(phase_r_root / "checkout_verification.json")

    if checkout.get("all_passed") is not True:
        raise ValueError("Phase-R checkout evidence failed")

    if len(worklist) != EXPECTED_CANDIDATES:
        raise ValueError("A1 worklist must contain 11 candidates")

    ready_ids = {str(item["candidate_id"]) for item in worklist}

    if len(ready_ids) != EXPECTED_CANDIDATES:
        raise ValueError("A1 worklist contains duplicate IDs")

    manifest_by_id = {
        str(item["candidate_id"]): item
        for item in manifests
        if (str(item["candidate_id"]) in ready_ids)
    }

    source_by_id = {
        str(item["candidate_id"]): item
        for item in sources
        if (str(item["candidate_id"]) in ready_ids)
    }

    probe_by_id = {
        str(item["candidate_id"]): item
        for item in probes
        if (str(item["candidate_id"]) in ready_ids)
    }

    if set(manifest_by_id) != ready_ids:
        raise ValueError("binding manifest coverage mismatch")

    if set(source_by_id) != ready_ids:
        raise ValueError("source slice coverage mismatch")

    if set(probe_by_id) != ready_ids:
        raise ValueError("symbolic probe coverage mismatch")

    validated_contracts = _validated_semantic_contracts(repo_root)

    proofs: list[JsonDict] = []

    for candidate_id in sorted(ready_ids):
        proofs.append(
            _proof_candidate(
                candidate_id=candidate_id,
                source_record=source_by_id[candidate_id],
                manifest=manifest_by_id[candidate_id],
                probe=probe_by_id[candidate_id],
                validated_contracts=validated_contracts,
            )
        )

    proved = [item for item in proofs if (item["status"] == "PROVED_A1_SOURCE_TO_BSIR")]

    review = [item for item in proofs if (item["status"] != "PROVED_A1_SOURCE_TO_BSIR")]

    protocol = _protocol_a1(repo_root / "experiments/V0.11_PROTOCOL.md")

    certificate_dir = output_dir / "certificates"

    certificate_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    certificates: list[JsonDict] = []

    for proof in proved:
        candidate_id = str(proof["candidate_id"])

        certificate_id = "CERT-V011-A1-" + candidate_id.upper()

        certificate: JsonDict = {
            "schema_version": "BIZPROOF-V0.11-A1-CERTIFICATE-1",
            "certificate_id": certificate_id,
            "candidate_id": candidate_id,
            "status": "CERTIFIED_A1",
            "terminal_outcome": "CERTIFIED_A1",
            "assistance_level": "A1",
            "protocol_definition": protocol,
            "claim_scope": (
                "Certification applies to the "
                "locked source function under the "
                "declared source-to-BVC call bindings "
                "and any explicitly listed validated "
                "semantic-contract abstractions."
            ),
            "source": {
                "source_id": proof["source"],
                "class": proof["class"],
                "function": proof["function"],
                "resolved_commit": EXPECTED_OPENFISCA_COMMIT,
                "source_file_sha256": proof["source_file_sha256"],
                "function_sha256": proof["source_function_sha256"],
            },
            "bindings": {
                "mechanism": ("DECLARATIVE_SOURCE_TO_BVC_BINDINGS_ONLY"),
                "count": proof["structural_binding_count"],
                "manifest_sha256": proof["binding_manifest_sha256"],
            },
            "semantic_contract_abstractions": proof["semantic_contract_abstractions"],
            "bsir": {
                "version": "BSIR-SKELETON-0.11",
                "ir_sha256": proof["probe_ir_sha256"],
            },
            "proof": {
                "proof_digest": proof["proof_digest"],
                "correct_solver_status": proof["solver"]["correct"],
                "mutant_solver_status": proof["solver"]["mutant"],
                "concrete_replay_cases": proof["replay_cases"],
                "mutation": proof["mutation"],
                "mutant_witness": proof["mutant_witness"],
                "obligations": proof["proof_obligations"],
            },
            "explicit_scalar_adapter": False,
            "terminal_outcome_assigned": True,
            "final_study_complete": False,
        }

        certificate["certificate_digest"] = _canonical_digest(dict(certificate))

        certificate_path = certificate_dir / (certificate_id + ".json")

        certificate_path.write_text(
            json.dumps(
                certificate,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        certificates.append(certificate)

    phase_q_states = _load_jsonl(
        repo_root / ("benchmarks/v0.11/terminal_certification/candidate_terminal_state.jsonl")
    )

    if len(phase_q_states) != 90:
        raise ValueError("Phase-Q terminal ledger must contain 90 candidates")

    certificate_by_id = {str(item["candidate_id"]): item for item in certificates}

    updated_states: list[JsonDict] = []

    for old in phase_q_states:
        candidate_id = str(old["candidate_id"])

        if candidate_id in certificate_by_id:
            if old["state"] != "PENDING_UNASSIGNED":
                raise ValueError("refusing to overwrite prior terminal outcome for " + candidate_id)

            certificate = certificate_by_id[candidate_id]

            updated_states.append(
                {
                    "candidate_id": candidate_id,
                    "state": "TERMINAL_ASSIGNED",
                    "terminal_outcome": "CERTIFIED_A1",
                    "certificate_id": certificate["certificate_id"],
                    "certificate_digest": certificate["certificate_digest"],
                }
            )

        else:
            updated_states.append(dict(old))

    assigned = [item for item in updated_states if (item["state"] == "TERMINAL_ASSIGNED")]

    pending = [item for item in updated_states if (item["state"] == "PENDING_UNASSIGNED")]

    a1_count = sum(1 for item in assigned if (item["terminal_outcome"] == "CERTIFIED_A1"))

    a2_count = sum(1 for item in assigned if (item["terminal_outcome"] == "CERTIFIED_A2"))

    if a2_count != EXPECTED_PHASE_Q_A2:
        raise ValueError("Phase-Q A2 certificate disappeared")

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (output_dir / "proofs.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in proofs
        ),
        encoding="utf-8",
    )

    (output_dir / "candidate_terminal_state.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in updated_states
        ),
        encoding="utf-8",
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "BATCH_A1_SYMBOLIC_PROOFS",
        "a1_candidates_attempted": len(proofs),
        "a1_candidates_proved": len(proved),
        "a1_candidates_review_required": len(review),
        "a1_certificates_issued": len(certificates),
        "a1_certified_candidate_ids": [item["candidate_id"] for item in certificates],
        "review_required": [
            {
                "candidate_id": item["candidate_id"],
                "reason": item.get("review_reason"),
            }
            for item in review
        ],
        "terminal_outcomes_assigned_total": len(assigned),
        "terminal_outcomes_pending": len(pending),
        "terminal_distribution": {
            "CERTIFIED_A0": 0,
            "CERTIFIED_A1": a1_count,
            "CERTIFIED_A2": a2_count,
        },
        "weighted_metrics_ready": False,
        "final_certification_complete": False,
        "passed": (len(proofs) == EXPECTED_CANDIDATES and len(assigned) + len(pending) == 90),
    }

    (output_dir / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "REVIEWER_REPORT.md").write_text(
        "\n".join(
            [
                ("# BIZPROOF V0.11 Batch A1 Symbolic Proofs"),
                "",
                (f"- A1 candidates attempted: {len(proofs)}"),
                (f"- A1 candidates proved: {len(proved)}"),
                (f"- A1 certificates issued: {len(certificates)}"),
                (f"- A1 review-required: {len(review)}"),
                (f"- Total terminal outcomes: {len(assigned)}/90"),
                (f"- Remaining pending: {len(pending)}/90"),
                "",
                (
                    "A1 proofs use an independent "
                    "source-AST compiler and a BSIR "
                    "compiler over the same declared "
                    "source-to-BVC bindings. "
                    "Certification is issued only when "
                    "the disequality query is UNSAT and "
                    "a deterministic structural mutant "
                    "produces a SAT witness that replays "
                    "concretely."
                ),
                "",
                (
                    "Candidates outside the supported "
                    "proof subset remain pending rather "
                    "than being promoted to a positive "
                    "terminal outcome."
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )

    return summary


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/a1_batch_proofs"),
    )

    args = parser.parse_args()

    summary = build_batch(
        repo_root=args.repo_root.resolve(),
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 batch A1 proofs")

    print(
        "Attempted:",
        summary["a1_candidates_attempted"],
    )

    print(
        "PROVED:",
        summary["a1_candidates_proved"],
    )

    print(
        "CERTIFIED_A1:",
        summary["a1_certificates_issued"],
    )

    print(
        "Review required:",
        summary["a1_candidates_review_required"],
    )

    print(
        "Terminal outcomes total:",
        summary["terminal_outcomes_assigned_total"],
        "/90",
    )

    print(
        "Pending:",
        summary["terminal_outcomes_pending"],
        "/90",
    )

    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
