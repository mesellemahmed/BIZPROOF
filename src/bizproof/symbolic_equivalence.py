from __future__ import annotations

import argparse
import ast
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeAlias

import z3

from .adapter_preservation import _checkout_commit

JsonDict = dict[str, Any]
Z3Expr: TypeAlias = Any


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> JsonDict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _find_method(
    path: Path,
    class_name: str,
    method_name: str,
) -> tuple[str, ast.FunctionDef]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name != class_name:
            continue

        for child in node.body:
            if isinstance(child, ast.FunctionDef) and child.name == method_name:
                return source, child

    raise ValueError(f"method {class_name}.{method_name} not found in {path}")


def _find_function(
    path: Path,
    function_name: str,
) -> tuple[str, ast.FunctionDef]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return source, node

    raise ValueError(f"function {function_name!r} not found in {path}")


def _node_hash(source: str, node: ast.AST) -> str:
    segment = ast.get_source_segment(source, node) or ast.unparse(node)
    return _sha256_bytes(segment.encode("utf-8"))


@dataclass
class SymbolicContext:
    symbols: dict[str, Z3Expr]
    call_bindings: dict[str, str]
    attribute_bindings: dict[str, str]
    method_call_bindings: dict[str, str]
    locals: dict[str, Z3Expr] = field(default_factory=dict)


def _binding_symbol(ctx: SymbolicContext, symbol_name: str) -> Z3Expr:
    try:
        return ctx.symbols[symbol_name]
    except KeyError as exc:
        raise ValueError(f"unknown symbolic input: {symbol_name}") from exc


def _translate_call(node: ast.Call, ctx: SymbolicContext) -> Z3Expr:
    if isinstance(node.func, ast.Name):
        name = node.func.id

        if name == "not_" and len(node.args) == 1:
            return z3.Not(_translate_expr(node.args[0], ctx))

        if name == "max_" and len(node.args) == 2:
            left = _translate_expr(node.args[0], ctx)
            right = _translate_expr(node.args[1], ctx)
            return z3.If(left >= right, left, right)

        if node.args and isinstance(node.args[0], ast.Constant):
            first = node.args[0].value
            if isinstance(first, str):
                key = f"{name}:{first}"
                if key in ctx.call_bindings:
                    return _binding_symbol(
                        ctx,
                        ctx.call_bindings[key],
                    )

    if isinstance(node.func, ast.Attribute):
        function_path = ast.unparse(node.func)

        if function_path in ctx.method_call_bindings:
            return _binding_symbol(
                ctx,
                ctx.method_call_bindings[function_path],
            )

    raise ValueError(f"unsupported call: {ast.unparse(node)}")


def _translate_compare(node: ast.Compare, ctx: SymbolicContext) -> Z3Expr:
    operands = [node.left, *node.comparators]
    translated = [_translate_expr(item, ctx) for item in operands]
    clauses: list[Z3Expr] = []

    for index, operator in enumerate(node.ops):
        left = translated[index]
        right = translated[index + 1]

        if isinstance(operator, ast.Eq):
            clause = left == right
        elif isinstance(operator, ast.NotEq):
            clause = left != right
        elif isinstance(operator, ast.Lt):
            clause = left < right
        elif isinstance(operator, ast.LtE):
            clause = left <= right
        elif isinstance(operator, ast.Gt):
            clause = left > right
        elif isinstance(operator, ast.GtE):
            clause = left >= right
        else:
            raise ValueError(f"unsupported comparison operator: {type(operator).__name__}")

        clauses.append(clause)

    if len(clauses) == 1:
        return clauses[0]
    return z3.And(*clauses)


def _translate_expr(node: ast.AST, ctx: SymbolicContext) -> Z3Expr:
    if isinstance(node, ast.Name):
        if node.id in ctx.locals:
            return ctx.locals[node.id]
        if node.id in ctx.symbols:
            return ctx.symbols[node.id]
        raise ValueError(f"unknown name: {node.id}")

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return z3.BoolVal(node.value)
        if isinstance(node.value, int):
            return z3.IntVal(node.value)
        raise ValueError(f"unsupported constant: {node.value!r}")

    if isinstance(node, ast.Attribute):
        path = ast.unparse(node)
        if path in ctx.attribute_bindings:
            return _binding_symbol(
                ctx,
                ctx.attribute_bindings[path],
            )
        raise ValueError(f"unsupported attribute: {path}")

    if isinstance(node, ast.Call):
        return _translate_call(node, ctx)

    if isinstance(node, ast.UnaryOp):
        value = _translate_expr(node.operand, ctx)

        if isinstance(node.op, ast.Not):
            return z3.Not(value)
        if isinstance(node.op, ast.USub):
            return -value

        raise ValueError(f"unsupported unary operator: {type(node.op).__name__}")

    if isinstance(node, ast.BoolOp):
        values = [_translate_expr(value, ctx) for value in node.values]

        if isinstance(node.op, ast.And):
            return z3.And(*values)
        if isinstance(node.op, ast.Or):
            return z3.Or(*values)

        raise ValueError(f"unsupported boolean operator: {type(node.op).__name__}")

    if isinstance(node, ast.BinOp):
        left = _translate_expr(node.left, ctx)
        right = _translate_expr(node.right, ctx)

        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right

        raise ValueError(f"unsupported binary operator: {type(node.op).__name__}")

    if isinstance(node, ast.Compare):
        return _translate_compare(node, ctx)

    if isinstance(node, ast.IfExp):
        return z3.If(
            _translate_expr(node.test, ctx),
            _translate_expr(node.body, ctx),
            _translate_expr(node.orelse, ctx),
        )

    raise ValueError(f"unsupported expression node: {type(node).__name__}")


def _strip_docstring(statements: list[ast.stmt]) -> list[ast.stmt]:
    if not statements:
        return statements

    first = statements[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return statements[1:]

    return statements


def _compile_statements(
    statements: list[ast.stmt],
    ctx: SymbolicContext,
) -> Z3Expr:
    remaining = _strip_docstring(statements)
    index = 0

    while index < len(remaining):
        statement = remaining[index]

        if isinstance(statement, ast.Assign):
            if len(statement.targets) != 1:
                raise ValueError("multiple assignment targets are unsupported")

            target = statement.targets[0]
            if not isinstance(target, ast.Name):
                raise ValueError(f"unsupported assignment target: {ast.unparse(target)}")

            ctx.locals[target.id] = _translate_expr(
                statement.value,
                ctx,
            )
            index += 1
            continue

        if isinstance(statement, ast.AnnAssign):
            if not isinstance(statement.target, ast.Name):
                raise ValueError("unsupported annotated assignment target")
            if statement.value is None:
                raise ValueError("assignment without value is unsupported")

            ctx.locals[statement.target.id] = _translate_expr(
                statement.value,
                ctx,
            )
            index += 1
            continue

        if isinstance(statement, ast.Return):
            if statement.value is None:
                raise ValueError("return without value is unsupported")
            return _translate_expr(statement.value, ctx)

        if isinstance(statement, ast.If):
            condition = _translate_expr(statement.test, ctx)

            then_ctx = SymbolicContext(
                symbols=ctx.symbols,
                call_bindings=ctx.call_bindings,
                attribute_bindings=ctx.attribute_bindings,
                method_call_bindings=ctx.method_call_bindings,
                locals=dict(ctx.locals),
            )
            else_ctx = SymbolicContext(
                symbols=ctx.symbols,
                call_bindings=ctx.call_bindings,
                attribute_bindings=ctx.attribute_bindings,
                method_call_bindings=ctx.method_call_bindings,
                locals=dict(ctx.locals),
            )

            then_expr = _compile_statements(
                statement.body + remaining[index + 1 :],
                then_ctx,
            )

            else_statements = (
                statement.orelse + remaining[index + 1 :]
                if statement.orelse
                else remaining[index + 1 :]
            )
            else_expr = _compile_statements(
                else_statements,
                else_ctx,
            )

            return z3.If(condition, then_expr, else_expr)

        raise ValueError(f"unsupported statement node: {type(statement).__name__}")

    raise ValueError("function has no symbolic return expression")


def _make_symbols(inputs: JsonDict) -> tuple[dict[str, Z3Expr], list[Z3Expr]]:
    symbols: dict[str, Z3Expr] = {}
    constraints: list[Z3Expr] = []

    for name, raw_spec in inputs.items():
        if not isinstance(raw_spec, dict):
            raise ValueError(f"invalid input spec: {name}")

        input_type = str(raw_spec["type"])

        if input_type == "bool":
            symbol = z3.Bool(name)
        elif input_type == "int":
            symbol = z3.Int(name)

            if "min" in raw_spec:
                constraints.append(symbol >= int(raw_spec["min"]))
            if "max" in raw_spec:
                constraints.append(symbol <= int(raw_spec["max"]))
        else:
            raise ValueError(f"unsupported input type: {input_type}")

        symbols[name] = symbol

    return symbols, constraints


def _new_context(rule: JsonDict, symbols: dict[str, Z3Expr]) -> SymbolicContext:
    return SymbolicContext(
        symbols=symbols,
        call_bindings={
            str(key): str(value) for key, value in dict(rule.get("call_bindings", {})).items()
        },
        attribute_bindings={
            str(key): str(value) for key, value in dict(rule.get("attribute_bindings", {})).items()
        },
        method_call_bindings={
            str(key): str(value)
            for key, value in dict(rule.get("method_call_bindings", {})).items()
        },
    )


def _external_expression(
    rule: JsonDict,
    external_path: Path,
    symbols: dict[str, Z3Expr],
) -> tuple[Z3Expr, JsonDict]:
    source, method = _find_method(
        external_path,
        str(rule["external_class"]),
        str(rule["external_method"]),
    )

    mode = str(rule["external_mode"])
    ctx = _new_context(rule, symbols)

    if mode == "FULL_FUNCTION":
        expression = _compile_statements(method.body, ctx)
        selected_node: ast.AST = method

    elif mode == "IF_CONDITION":
        anchor = str(rule["condition_anchor"])
        selected_if: ast.If | None = None

        for node in ast.walk(method):
            if not isinstance(node, ast.If):
                continue
            if ast.unparse(node.test) == anchor:
                selected_if = node
                break

        if selected_if is None:
            raise ValueError(f"condition {anchor!r} not found in external method")

        expression = _translate_expr(selected_if.test, ctx)
        selected_node = selected_if.test

    else:
        raise ValueError(f"unsupported external mode: {mode}")

    metadata = {
        "external_mode": mode,
        "external_source_sha256": _sha256_file(external_path),
        "external_method_sha256": _node_hash(source, method),
        "external_slice_sha256": _node_hash(source, selected_node),
        "external_method_lines": {
            "start": method.lineno,
            "end": getattr(method, "end_lineno", method.lineno),
        },
        "external_slice": ast.unparse(selected_node),
    }
    return expression, metadata


def _adapter_expression(
    path: Path,
    function_name: str,
    symbols: dict[str, Z3Expr],
) -> tuple[Z3Expr, JsonDict]:
    source, function = _find_function(path, function_name)

    context = SymbolicContext(
        symbols=symbols,
        call_bindings={},
        attribute_bindings={},
        method_call_bindings={},
    )

    expression = _compile_statements(function.body, context)

    return expression, {
        "adapter_file_sha256": _sha256_file(path),
        "adapter_function_sha256": _node_hash(source, function),
        "adapter_function_lines": {
            "start": function.lineno,
            "end": getattr(function, "end_lineno", function.lineno),
        },
    }


def _model_to_json(
    model: z3.ModelRef,
    inputs: JsonDict,
    symbols: dict[str, Z3Expr],
) -> JsonDict:
    result: JsonDict = {}

    for name, raw_spec in inputs.items():
        if not isinstance(raw_spec, dict):
            continue

        value = model.eval(
            symbols[name],
            model_completion=True,
        )

        if str(raw_spec["type"]) == "bool":
            result[name] = z3.is_true(value)
        else:
            result[name] = value.as_long()

    return result


def _prove_equivalence(
    external: Z3Expr,
    candidate: Z3Expr,
    constraints: list[Z3Expr],
    inputs: JsonDict,
    symbols: dict[str, Z3Expr],
) -> JsonDict:
    solver = z3.Solver()

    if constraints:
        solver.add(*constraints)

    solver.add(external != candidate)

    started = time.perf_counter()
    status = solver.check()
    elapsed = time.perf_counter() - started

    if status == z3.unsat:
        return {
            "verdict": "PROVED",
            "solver_status": "unsat",
            "counterexample": None,
            "runtime_seconds": elapsed,
        }

    if status == z3.sat:
        return {
            "verdict": "DISPROVED",
            "solver_status": "sat",
            "counterexample": _model_to_json(
                solver.model(),
                inputs,
                symbols,
            ),
            "runtime_seconds": elapsed,
        }

    return {
        "verdict": "UNKNOWN",
        "solver_status": "unknown",
        "counterexample": None,
        "runtime_seconds": elapsed,
        "reason": solver.reason_unknown(),
    }


def run_symbolic_equivalence(
    *,
    catalog_path: Path,
    lock_path: Path,
    external_root: Path,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:
    catalog = _load_json(catalog_path)
    lock = _load_json(lock_path)

    raw_sources = lock.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("lock sources must be a list")

    locked = {
        str(item["id"]): item for item in raw_sources if isinstance(item, dict) and "id" in item
    }

    raw_rules = catalog.get("rules")
    if not isinstance(raw_rules, list):
        raise ValueError("catalog rules must be a list")

    details: list[JsonDict] = []
    failures: list[JsonDict] = []
    started = time.perf_counter()

    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            raise ValueError("rule must be an object")

        rule = raw_rule
        rule_id = str(rule["id"])

        try:
            source_id = str(rule["source_id"])
            expected_commit = str(rule["resolved_commit"])

            if source_id not in locked:
                raise ValueError(f"source not present in lock: {source_id}")

            locked_commit = str(locked[source_id]["resolved_commit"])
            checkout_commit = _checkout_commit(external_root / source_id)

            if not (expected_commit == locked_commit == checkout_commit):
                raise ValueError("catalog/lock/checkout commit mismatch")

            raw_inputs = rule.get("inputs")
            if not isinstance(raw_inputs, dict):
                raise ValueError("inputs must be an object")

            inputs: JsonDict = raw_inputs
            symbols, constraints = _make_symbols(inputs)

            external_path = external_root / source_id / str(rule["external_source"])
            adapter_path = repo_root / str(rule["adapter"])

            external_expr, external_metadata = _external_expression(
                rule,
                external_path,
                symbols,
            )

            adapter_expr, adapter_metadata = _adapter_expression(
                adapter_path,
                str(rule["adapter_function"]),
                symbols,
            )

            mutant_expr, mutant_metadata = _adapter_expression(
                adapter_path,
                str(rule["mutant_function"]),
                symbols,
            )

            correct = _prove_equivalence(
                external_expr,
                adapter_expr,
                constraints,
                inputs,
                symbols,
            )
            mutant = _prove_equivalence(
                external_expr,
                mutant_expr,
                constraints,
                inputs,
                symbols,
            )

            expected_correct = str(rule["expected_correct"])
            expected_mutant = str(rule["expected_mutant"])

            details.append(
                {
                    "rule_id": rule_id,
                    "source_id": source_id,
                    "resolved_commit": expected_commit,
                    "external_source": str(rule["external_source"]),
                    "external_class": str(rule["external_class"]),
                    "external_method": str(rule["external_method"]),
                    "domain": inputs,
                    "external_symbolic_expression": str(z3.simplify(external_expr)),
                    "adapter_symbolic_expression": str(z3.simplify(adapter_expr)),
                    "mutant_symbolic_expression": str(z3.simplify(mutant_expr)),
                    **external_metadata,
                    **adapter_metadata,
                    "mutant_function_sha256": mutant_metadata["adapter_function_sha256"],
                    "correct": correct,
                    "mutant": mutant,
                    "expected_correct": expected_correct,
                    "expected_mutant": expected_mutant,
                    "passed": (
                        correct["verdict"] == expected_correct
                        and mutant["verdict"] == expected_mutant
                        and mutant["counterexample"] is not None
                    ),
                }
            )

        except (
            KeyError,
            OSError,
            TypeError,
            ValueError,
            z3.Z3Exception,
        ) as exc:
            failures.append(
                {
                    "rule_id": rule_id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    rules_passed = sum(1 for item in details if item["passed"])
    correct_proved = sum(1 for item in details if item["correct"]["verdict"] == "PROVED")
    mutants_disproved = sum(1 for item in details if item["mutant"]["verdict"] == "DISPROVED")
    unknown_results = sum(
        1 for item in details for key in ("correct", "mutant") if item[key]["verdict"] == "UNKNOWN"
    )

    passed = (
        not failures
        and len(details) == len(raw_rules)
        and rules_passed == len(raw_rules)
        and correct_proved == len(raw_rules)
        and mutants_disproved == len(raw_rules)
        and unknown_results == 0
    )

    summary: JsonDict = {
        "benchmark_version": "0.9.0",
        "claim_scope": catalog["claim_scope"],
        "rules_configured": len(raw_rules),
        "rules_checked": len(details),
        "rules_passed": rules_passed,
        "correct_equivalences_proved": correct_proved,
        "mutants_disproved": mutants_disproved,
        "unknown_results": unknown_results,
        "failures": failures,
        "runtime_seconds": time.perf_counter() - started,
        "passed": passed,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "details.json").write_text(
        json.dumps(details, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prove symbolic equivalence of external semantic slices and adapters."
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("benchmarks/v0.9/catalog.json"),
    )
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path("benchmarks/v0.6/LOCK.json"),
    )
    parser.add_argument(
        "--external-root",
        type=Path,
        default=Path("external_sources/v0.6"),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.9/results"),
    )
    args = parser.parse_args()

    summary = run_symbolic_equivalence(
        catalog_path=args.catalog,
        lock_path=args.lock,
        external_root=args.external_root,
        repo_root=args.repo_root,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.9 symbolic adapter equivalence certification")
    print(
        "Correct equivalences proved: "
        f"{summary['correct_equivalences_proved']}/"
        f"{summary['rules_configured']}"
    )
    print(f"Mutants disproved: {summary['mutants_disproved']}/{summary['rules_configured']}")
    print(f"UNKNOWN results: {summary['unknown_results']}")
    print(f"Failures: {len(summary['failures'])}")
    print(f"Runtime seconds: {summary['runtime_seconds']:.6f}")
    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
