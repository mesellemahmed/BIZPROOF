from __future__ import annotations

import argparse
import json
import tempfile
import time
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from hypothesis import Phase, find, settings
from hypothesis import strategies as st
from hypothesis.errors import NoSuchExample

from .baseline_comparison import _input_specs, _run_crosshair, _write_candidate_source
from .loader import load_function
from .model import BusinessContract, TargetSpec, Verdict
from .z3_backend import verify_with_z3

Rule = dict[str, Any]


def _function_signature(rule: Rule) -> tuple[str, list[str]]:
    inputs = rule.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("invalid inputs")

    parameters: list[str] = []
    names: list[str] = []
    for name, raw_spec in inputs.items():
        if not isinstance(raw_spec, dict):
            raise ValueError(f"invalid input spec for {name}")
        type_name = raw_spec.get("type")
        if type_name == "int":
            annotation = "int"
        elif type_name == "bool":
            annotation = "bool"
        else:
            raise ValueError(f"unsupported type for {name}: {type_name}")
        names.append(str(name))
        parameters.append(f"{name}: {annotation}")
    return ", ".join(parameters), names


def _write_crosshair_source(path: Path, rule: Rule, expression: str) -> None:
    signature, names = _function_signature(rule)
    arguments = ", ".join(names)
    inputs = rule.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("invalid inputs")

    assertions: list[str] = []
    for name, raw_spec in inputs.items():
        if not isinstance(raw_spec, dict):
            raise ValueError(f"invalid input spec for {name}")
        if raw_spec.get("type") == "int":
            minimum = raw_spec.get("min")
            maximum = raw_spec.get("max")
            if not isinstance(minimum, int) or not isinstance(maximum, int):
                raise ValueError(f"integer input {name} requires min/max")
            assertions.append(f"    assert {name} >= {minimum}")
            assertions.append(f"    assert {name} <= {maximum}")

    lines = [
        f"def target({signature}) -> bool:",
        f"    return {expression}",
        "",
        f"def check_business_rule({signature}) -> None:",
        *(assertions or ["    assert True"]),
        f"    observed = target({arguments})",
        f"    assert observed == ({reference_expression(rule)})",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _hypothesis_strategy(rule: Rule) -> st.SearchStrategy[dict[str, Any]]:
    inputs = rule.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("invalid inputs")

    fields: dict[str, st.SearchStrategy[Any]] = {}
    for name, raw_spec in inputs.items():
        if not isinstance(raw_spec, dict):
            raise ValueError(f"invalid input spec for {name}")
        type_name = raw_spec.get("type")
        if type_name == "bool":
            fields[str(name)] = st.booleans()
        elif type_name == "int":
            minimum = raw_spec.get("min")
            maximum = raw_spec.get("max")
            if not isinstance(minimum, int) or not isinstance(maximum, int):
                raise ValueError(f"integer input {name} requires min/max")
            fields[str(name)] = st.integers(min_value=minimum, max_value=maximum)
        else:
            raise ValueError(f"unsupported type for {name}: {type_name}")
    return st.fixed_dictionaries(fields)


def _run_hypothesis(
    rule: Rule,
    source: Path,
    *,
    max_examples: int,
) -> tuple[bool | None, dict[str, Any] | None, float, str | None]:
    started = time.perf_counter()
    try:
        target = load_function(source, "target")
        strategy = _hypothesis_strategy(rule)
        hypothesis_settings = settings(
            max_examples=max_examples,
            derandomize=True,
            database=None,
            deadline=None,
            phases=(Phase.generate, Phase.shrink),
        )
        witness = find(
            strategy,
            lambda values: (
                bool(target(**values))
                != bool(
                    eval(
                        compile(reference_expression(rule), "<bizproof-v05>", "eval"),
                        {"__builtins__": {}},
                        dict(values),
                    )
                )
            ),
            settings=hypothesis_settings,
        )
        return True, dict(witness), time.perf_counter() - started, None
    except NoSuchExample:
        return False, None, time.perf_counter() - started, None
    except Exception as exc:
        return None, None, time.perf_counter() - started, f"{type(exc).__name__}: {exc}"


FAMILIES = {
    "single_magic",
    "pair_magic",
    "narrow_boundary",
    "guarded_magic",
    "linear_magic",
    "triple_magic",
}


def load_catalog(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("challenge catalog must be a JSON object")
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("challenge catalog requires a non-empty rules list")
    return payload


def _params(rule: Rule) -> dict[str, int]:
    raw = rule.get("params")
    if not isinstance(raw, dict):
        raise ValueError(f"invalid params for {rule.get('id')}")
    result: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(value, int):
            raise ValueError(f"parameter {key} must be int")
        result[str(key)] = value
    return result


def reference_expression(rule: Rule) -> str:
    family = str(rule["family"])
    p = _params(rule)

    if family == "single_magic":
        return f"x != {p['target']}"
    if family == "pair_magic":
        return f"not ((x == {p['target_x']}) and (y == {p['target_y']}))"
    if family == "narrow_boundary":
        return f"not ((x >= {p['low']}) and (x <= {p['high']}))"
    if family == "guarded_magic":
        return f"(not flag) or (x != {p['target']})"
    if family == "linear_magic":
        return f"(x + y) != {p['target']}"
    if family == "triple_magic":
        return f"not ((x == {p['target_x']}) and (y == {p['target_y']}) and (z == {p['target_z']}))"
    raise ValueError(f"unsupported challenge family: {family}")


def mutant_expression(rule: Rule) -> str:
    family = str(rule["family"])
    p = _params(rule)

    if family == "single_magic":
        return f"x != {p['target'] + 1}"
    if family == "pair_magic":
        return f"not ((x == {p['target_x']}) and (y == {p['target_y'] + 1}))"
    if family == "narrow_boundary":
        return f"not ((x >= {p['low'] + 1}) and (x <= {p['high']}))"
    if family == "guarded_magic":
        return f"(not flag) or (x != {p['target'] + 1})"
    if family == "linear_magic":
        return f"(x + y) != {p['target'] + 1}"
    if family == "triple_magic":
        return (
            f"not ((x == {p['target_x']}) and "
            f"(y == {p['target_y']}) and (z == {p['target_z'] + 1}))"
        )
    raise ValueError(f"unsupported challenge family: {family}")


def _int_span(spec: Mapping[str, Any]) -> int:
    minimum = spec.get("min")
    maximum = spec.get("max")
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        raise ValueError("integer input requires min/max")
    return maximum - minimum + 1


def domain_size(rule: Rule) -> int:
    inputs = rule.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("invalid inputs")

    total = 1
    for raw in inputs.values():
        if not isinstance(raw, dict):
            raise ValueError("invalid input specification")
        if raw.get("type") == "bool":
            total *= 2
        elif raw.get("type") == "int":
            total *= _int_span(raw)
        else:
            raise ValueError("unsupported input type")
    return total


def witness_count(rule: Rule) -> int:
    family = str(rule["family"])
    p = _params(rule)

    if family in {"single_magic", "pair_magic", "guarded_magic", "triple_magic"}:
        return 2
    if family == "narrow_boundary":
        return 1
    if family == "linear_magic":
        inputs = rule["inputs"]
        if not isinstance(inputs, dict):
            raise ValueError("invalid inputs")
        x_spec = inputs["x"]
        y_spec = inputs["y"]
        if not isinstance(x_spec, dict) or not isinstance(y_spec, dict):
            raise ValueError("invalid linear input specs")
        x_min = x_spec["min"]
        x_max = x_spec["max"]
        y_min = y_spec["min"]
        y_max = y_spec["max"]
        if not all(isinstance(v, int) for v in (x_min, x_max, y_min, y_max)):
            raise ValueError("linear inputs require integer bounds")

        def solution_count(target: int) -> int:
            low = max(int(x_min), target - int(y_max))
            high = min(int(x_max), target - int(y_min))
            return max(0, high - low + 1)

        return solution_count(p["target"]) + solution_count(p["target"] + 1)

    raise ValueError(f"unsupported challenge family: {family}")


def validate_catalog(catalog: Mapping[str, Any]) -> None:
    rules = catalog.get("rules")
    if not isinstance(rules, list):
        raise ValueError("rules must be a list")

    ids: set[str] = set()
    domains: defaultdict[str, int] = defaultdict(int)

    for raw in rules:
        if not isinstance(raw, dict):
            raise ValueError("invalid rule")
        rule: Rule = raw
        rule_id = rule.get("id")
        family = rule.get("family")
        domain = rule.get("domain")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("rule id required")
        if rule_id in ids:
            raise ValueError(f"duplicate rule id: {rule_id}")
        ids.add(rule_id)
        if family not in FAMILIES:
            raise ValueError(f"unsupported family: {family}")
        if domain not in {"banking", "ecommerce", "insurance"}:
            raise ValueError(f"unsupported domain: {domain}")
        domains[str(domain)] += 1
        size = domain_size(rule)
        witnesses = witness_count(rule)
        if witnesses <= 0 or witnesses >= size:
            raise ValueError(f"invalid witness count for {rule_id}")

    if len(rules) == 30 and dict(domains) != {
        "banking": 10,
        "ecommerce": 10,
        "insurance": 10,
    }:
        raise ValueError(f"unexpected domain distribution: {dict(domains)}")


def reference_value(rule: Rule, values: Mapping[str, Any]) -> bool:
    return bool(
        eval(
            compile(reference_expression(rule), "<bizproof-v05>", "eval"),
            {"__builtins__": {}},
            dict(values),
        )
    )


def _write_challenge_crosshair_source(
    path: Path,
    rule: Rule,
    expression: str,
) -> None:
    _write_crosshair_source(path, rule, expression)


def _run_challenge_hypothesis(
    rule: Rule,
    source: Path,
    *,
    max_examples: int,
) -> tuple[bool | None, dict[str, Any] | None, float, str | None]:
    started = time.perf_counter()
    try:
        target = load_function(source, "target")
        strategy = _hypothesis_strategy(rule)
        hypothesis_settings = settings(
            max_examples=max_examples,
            derandomize=True,
            database=None,
            deadline=None,
            phases=(Phase.generate, Phase.shrink),
        )
        witness = find(
            strategy,
            lambda values: bool(target(**values)) != reference_value(rule, values),
            settings=hypothesis_settings,
        )
        return True, dict(witness), time.perf_counter() - started, None
    except NoSuchExample:
        return False, None, time.perf_counter() - started, None
    except Exception as exc:
        return None, None, time.perf_counter() - started, f"{type(exc).__name__}: {exc}"


def _new_budget_summary() -> dict[str, Any]:
    return {
        "mutants": 0,
        "mutants_detected": 0,
        "mutants_missed": 0,
        "mutants_inconclusive": 0,
        "correct_cases": 0,
        "correct_false_alarms": 0,
        "correct_inconclusive": 0,
        "runtime_seconds": 0.0,
    }


def _record(
    summary: dict[str, Any],
    *,
    mutant: bool,
    detected: bool | None,
    runtime: float,
) -> None:
    summary["runtime_seconds"] += runtime
    if mutant:
        summary["mutants"] += 1
        if detected is True:
            summary["mutants_detected"] += 1
        elif detected is False:
            summary["mutants_missed"] += 1
        else:
            summary["mutants_inconclusive"] += 1
    else:
        summary["correct_cases"] += 1
        if detected is True:
            summary["correct_false_alarms"] += 1
        else:
            summary["correct_inconclusive"] += 1


def _finalize(summary: dict[str, Any]) -> dict[str, Any]:
    mutants = int(summary["mutants"])
    correct = int(summary["correct_cases"])
    summary["mutant_detection_rate"] = summary["mutants_detected"] / mutants if mutants else 0.0
    summary["correct_false_alarm_rate"] = (
        summary["correct_false_alarms"] / correct if correct else 0.0
    )
    summary["runtime_seconds"] = round(float(summary["runtime_seconds"]), 6)
    return summary


def run_challenge(
    catalog_path: Path,
    output_path: Path,
    *,
    hypothesis_budgets: tuple[int, ...] = (100, 1000, 10000),
    crosshair_budgets: tuple[float, ...] = (0.5, 2.0),
    crosshair_process_timeout: float = 6.0,
) -> dict[str, Any]:
    catalog = load_catalog(catalog_path)
    validate_catalog(catalog)
    raw_rules = catalog["rules"]
    assert isinstance(raw_rules, list)

    hypothesis = {str(b): _new_budget_summary() for b in hypothesis_budgets}
    crosshair = {str(b): _new_budget_summary() for b in crosshair_budgets}
    bizproof: dict[str, Any] = {
        "cases": 0,
        "correct_cases": 0,
        "correct_proved": 0,
        "mutants": 0,
        "mutants_detected": 0,
        "unknown": 0,
        "false_proved": 0,
        "false_disproved": 0,
        "runtime_seconds": 0.0,
    }
    per_family: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "rules": 0,
            "domain_size_sum": 0,
            "witness_count_sum": 0,
            "min_witness_density": 1.0,
            "max_witness_density": 0.0,
        }
    )
    rows: list[dict[str, Any]] = []
    tool_errors: list[dict[str, str]] = []
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="bizproof-v05-") as tmp:
        workspace = Path(tmp)

        for raw_rule in raw_rules:
            if not isinstance(raw_rule, dict):
                raise ValueError("invalid rule")
            rule: Rule = raw_rule
            family = str(rule["family"])
            size = domain_size(rule)
            witnesses = witness_count(rule)
            density = witnesses / size

            family_bucket = per_family[family]
            family_bucket["rules"] += 1
            family_bucket["domain_size_sum"] += size
            family_bucket["witness_count_sum"] += witnesses
            family_bucket["min_witness_density"] = min(
                float(family_bucket["min_witness_density"]),
                density,
            )
            family_bucket["max_witness_density"] = max(
                float(family_bucket["max_witness_density"]),
                density,
            )

            variants = (
                ("correct", reference_expression(rule), False),
                ("rare_mutant", mutant_expression(rule), True),
            )

            for variant, expression, is_mutant in variants:
                source = workspace / f"{rule['id']}_{variant}.py"
                crosshair_source = workspace / f"{rule['id']}_{variant}_crosshair.py"
                _write_candidate_source(source, rule, expression)
                _write_challenge_crosshair_source(crosshair_source, rule, expression)

                contract = BusinessContract(
                    contract_id=f"{rule['id']}::{variant}",
                    title=str(rule.get("title", rule["id"])),
                    target=TargetSpec(source=source, function="target"),
                    inputs=_input_specs(rule),
                    precondition="True",
                    postcondition=f"result == ({reference_expression(rule)})",
                    expected_outcome=str(rule.get("business_text", "")),
                )

                biz_started = time.perf_counter()
                evidence = verify_with_z3(contract)
                biz_runtime = time.perf_counter() - biz_started
                bizproof["cases"] += 1
                bizproof["runtime_seconds"] += biz_runtime

                if is_mutant:
                    bizproof["mutants"] += 1
                    if evidence.verdict is Verdict.DISPROVED:
                        bizproof["mutants_detected"] += 1
                    elif evidence.verdict is Verdict.PROVED:
                        bizproof["false_proved"] += 1
                    else:
                        bizproof["unknown"] += 1
                else:
                    bizproof["correct_cases"] += 1
                    if evidence.verdict is Verdict.PROVED:
                        bizproof["correct_proved"] += 1
                    elif evidence.verdict is Verdict.DISPROVED:
                        bizproof["false_disproved"] += 1
                    else:
                        bizproof["unknown"] += 1

                row: dict[str, Any] = {
                    "rule_id": rule["id"],
                    "domain": rule["domain"],
                    "family": family,
                    "variant": variant,
                    "domain_size": size,
                    "witness_count": 0 if not is_mutant else witnesses,
                    "witness_density": 0.0 if not is_mutant else density,
                    "bizproof_verdict": evidence.verdict.value,
                    "bizproof_runtime_seconds": round(biz_runtime, 6),
                }

                for hypothesis_budget in hypothesis_budgets:
                    detected, witness, runtime, error = _run_challenge_hypothesis(
                        rule,
                        source,
                        max_examples=hypothesis_budget,
                    )
                    _record(
                        hypothesis[str(hypothesis_budget)],
                        mutant=is_mutant,
                        detected=detected,
                        runtime=runtime,
                    )
                    row[f"hypothesis_{hypothesis_budget}"] = (
                        "DETECTED"
                        if detected is True
                        else "NO_COUNTEREXAMPLE"
                        if detected is False
                        else "ERROR"
                    )
                    row[f"hypothesis_{hypothesis_budget}_runtime_seconds"] = round(runtime, 6)
                    row[f"hypothesis_{hypothesis_budget}_witness"] = (
                        json.dumps(witness, sort_keys=True) if witness is not None else ""
                    )
                    row[f"hypothesis_{hypothesis_budget}_error"] = error or ""
                    if error is not None:
                        tool_errors.append(
                            {
                                "tool": "hypothesis",
                                "hypothesis_budget": str(hypothesis_budget),
                                "case": f"{rule['id']}::{variant}",
                                "error": error,
                            }
                        )

                for crosshair_budget in crosshair_budgets:
                    detected, runtime, error = _run_crosshair(
                        crosshair_source,
                        per_condition_timeout=crosshair_budget,
                        process_timeout=crosshair_process_timeout,
                    )
                    _record(
                        crosshair[str(crosshair_budget)],
                        mutant=is_mutant,
                        detected=detected,
                        runtime=runtime,
                    )
                    label = str(crosshair_budget).replace(".", "_")
                    row[f"crosshair_{label}"] = (
                        "DETECTED"
                        if detected is True
                        else "NO_COUNTEREXAMPLE"
                        if detected is False
                        else "INCONCLUSIVE"
                    )
                    row[f"crosshair_{label}_runtime_seconds"] = round(runtime, 6)
                    row[f"crosshair_{label}_error"] = error or ""
                    if error is not None and error != "process_timeout":
                        tool_errors.append(
                            {
                                "tool": "crosshair",
                                "crosshair_budget": str(crosshair_budget),
                                "case": f"{rule['id']}::{variant}",
                                "error": error,
                            }
                        )

                rows.append(row)

    finalized_hypothesis = {budget: _finalize(summary) for budget, summary in hypothesis.items()}
    finalized_crosshair = {budget: _finalize(summary) for budget, summary in crosshair.items()}
    bizproof["runtime_seconds"] = round(float(bizproof["runtime_seconds"]), 6)
    bizproof["mutant_detection_rate"] = (
        bizproof["mutants_detected"] / bizproof["mutants"] if bizproof["mutants"] else 0.0
    )
    bizproof["proof_rate_on_correct"] = (
        bizproof["correct_proved"] / bizproof["correct_cases"] if bizproof["correct_cases"] else 0.0
    )

    passed = (
        bizproof["false_proved"] == 0
        and bizproof["false_disproved"] == 0
        and bizproof["unknown"] == 0
        and bizproof["mutants_detected"] == bizproof["mutants"]
        and bizproof["correct_proved"] == bizproof["correct_cases"]
        and not tool_errors
    )

    summary: dict[str, Any] = {
        "benchmark_version": "0.5.0",
        "catalog": str(catalog_path),
        "rules_checked": len(raw_rules),
        "cases_checked": len(rows),
        "bizproof": bizproof,
        "hypothesis_by_budget": finalized_hypothesis,
        "crosshair_by_budget": finalized_crosshair,
        "tool_errors": tool_errors,
        "per_family": {
            family: {
                **bucket,
                "min_witness_density": float(bucket["min_witness_density"]),
                "max_witness_density": float(bucket["max_witness_density"]),
            }
            for family, bucket in sorted(per_family.items())
        },
        "wall_runtime_seconds": round(time.perf_counter() - started, 6),
        "interpretation": {
            "bizproof_proved": "formal proof within the supported BIZPROOF semantics",
            "hypothesis_no_counterexample": "inconclusive under the configured search budget",
            "crosshair_no_counterexample": (
                "inconclusive under the configured symbolic-analysis budget"
            ),
        },
        "passed": passed,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    details_path = output_path.with_name("v0.5-challenge-details.json")
    details_path.write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _print_budget(name: str, budgets: Mapping[str, Any]) -> None:
    print(name)
    for budget, raw in budgets.items():
        if not isinstance(raw, dict):
            continue
        print(
            f"  budget={budget}: "
            f"detected={raw['mutants_detected']}/{raw['mutants']} "
            f"rate={raw['mutant_detection_rate']:.6f} "
            f"false_alarms={raw['correct_false_alarms']} "
            f"inconclusive_mutants={raw['mutants_inconclusive']} "
            f"runtime={raw['runtime_seconds']:.3f}s"
        )


def _print_summary(summary: Mapping[str, Any]) -> None:
    print("BIZPROOF V0.5 rare-witness challenge")
    print(f"Rules checked: {summary['rules_checked']}")
    print(f"Cases checked: {summary['cases_checked']}")
    biz = summary["bizproof"]
    if not isinstance(biz, dict):
        raise ValueError("invalid BIZPROOF summary")
    print(
        "BIZPROOF: "
        f"mutants={biz['mutants_detected']}/{biz['mutants']} "
        f"correct_proved={biz['correct_proved']}/{biz['correct_cases']} "
        f"unknown={biz['unknown']} "
        f"runtime={biz['runtime_seconds']:.3f}s"
    )
    hyp = summary["hypothesis_by_budget"]
    cross = summary["crosshair_by_budget"]
    if isinstance(hyp, dict):
        _print_budget("Hypothesis", hyp)
    if isinstance(cross, dict):
        _print_budget("CrossHair", cross)
    print(f"Wall runtime seconds: {summary['wall_runtime_seconds']:.3f}")
    print("PASS" if summary["passed"] else "FAIL")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the BIZPROOF V0.5 challenge benchmark")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("benchmarks/v0.5/catalog.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/results/v0.5-challenge-summary.json"),
    )
    args = parser.parse_args()

    summary = run_challenge(args.catalog, args.output)
    _print_summary(summary)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
