from __future__ import annotations

import argparse
import itertools
import json
import tempfile
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .loader import load_function
from .model import BusinessContract, InputSpec, TargetSpec, Verdict

Rule = dict[str, Any]

FAMILIES = {
    "threshold_or_flag",
    "threshold_and_flag",
    "range_and_flag",
    "dual_and",
    "dual_or",
    "not_blocked_threshold",
    "two_bool_and",
    "two_bool_or",
    "tiered_threshold",
    "conditional_flag",
}


def load_catalog(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("benchmark catalog must be a JSON object")
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("benchmark catalog must contain a non-empty rules list")
    return payload


def validate_catalog(catalog: Mapping[str, Any]) -> None:
    rules_raw = catalog.get("rules")
    if not isinstance(rules_raw, list):
        raise ValueError("rules must be a list")

    ids: set[str] = set()
    domains: Counter[str] = Counter()
    families: Counter[str] = Counter()

    for raw_rule in rules_raw:
        if not isinstance(raw_rule, dict):
            raise ValueError("each rule must be an object")
        rule_id = raw_rule.get("id")
        domain = raw_rule.get("domain")
        family = raw_rule.get("family")
        inputs = raw_rule.get("inputs")
        business_text = raw_rule.get("business_text")

        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("every rule requires a non-empty id")
        if rule_id in ids:
            raise ValueError(f"duplicate rule id: {rule_id}")
        ids.add(rule_id)

        if domain not in {"banking", "ecommerce", "insurance"}:
            raise ValueError(f"unsupported domain for {rule_id}: {domain}")
        if family not in FAMILIES:
            raise ValueError(f"unsupported family for {rule_id}: {family}")
        if not isinstance(inputs, dict) or not inputs:
            raise ValueError(f"rule {rule_id} requires inputs")
        if not isinstance(business_text, str) or not business_text:
            raise ValueError(f"rule {rule_id} requires business_text")

        domains[str(domain)] += 1
        families[str(family)] += 1

    if len(rules_raw) == 60:
        if domains != Counter({"banking": 20, "ecommerce": 20, "insurance": 20}):
            raise ValueError(f"unexpected domain distribution: {dict(domains)}")
        expected_family_distribution = Counter({family: 6 for family in FAMILIES})
        if families != expected_family_distribution:
            raise ValueError(f"unexpected family distribution: {dict(families)}")


def _param(rule: Rule, name: str) -> int:
    params = rule.get("params")
    if not isinstance(params, dict):
        raise ValueError(f"rule {rule.get('id')} has invalid params")
    value = params.get(name)
    if not isinstance(value, int):
        raise ValueError(f"rule {rule.get('id')} missing integer parameter {name}")
    return value


def reference_expression(rule: Rule) -> str:
    family = str(rule["family"])

    if family == "threshold_or_flag":
        threshold = _param(rule, "threshold")
        return f"(x >= {threshold}) or flag"
    if family == "threshold_and_flag":
        threshold = _param(rule, "threshold")
        return f"(x >= {threshold}) and flag"
    if family == "range_and_flag":
        low = _param(rule, "low")
        high = _param(rule, "high")
        return f"(x >= {low}) and (x <= {high}) and flag"
    if family == "dual_and":
        x_threshold = _param(rule, "x_threshold")
        y_threshold = _param(rule, "y_threshold")
        return f"(x >= {x_threshold}) and (y >= {y_threshold})"
    if family == "dual_or":
        x_threshold = _param(rule, "x_threshold")
        y_threshold = _param(rule, "y_threshold")
        return f"(x >= {x_threshold}) or (y >= {y_threshold})"
    if family == "not_blocked_threshold":
        max_x = _param(rule, "max_x")
        return f"(x <= {max_x}) and (not blocked)"
    if family == "two_bool_and":
        return "a and b"
    if family == "two_bool_or":
        return "a or b"
    if family == "tiered_threshold":
        premium_threshold = _param(rule, "premium_threshold")
        standard_threshold = _param(rule, "standard_threshold")
        return (
            f"(premium and (x >= {premium_threshold})) or "
            f"((not premium) and (x >= {standard_threshold}))"
        )
    if family == "conditional_flag":
        threshold = _param(rule, "threshold")
        return f"((x >= {threshold}) and flag) or ((x < {threshold}) and fallback)"

    raise ValueError(f"unsupported family: {family}")


def implementation_variants(rule: Rule) -> list[tuple[str, str]]:
    family = str(rule["family"])
    correct = reference_expression(rule)

    if family == "threshold_or_flag":
        threshold = _param(rule, "threshold")
        mutants = [
            ("boundary", f"(x > {threshold}) or flag"),
            ("join", f"(x >= {threshold}) and flag"),
            ("negate_flag", f"(x >= {threshold}) or (not flag)"),
            ("threshold_shift", f"(x >= {threshold + 1}) or flag"),
        ]
    elif family == "threshold_and_flag":
        threshold = _param(rule, "threshold")
        mutants = [
            ("boundary", f"(x > {threshold}) and flag"),
            ("join", f"(x >= {threshold}) or flag"),
            ("negate_flag", f"(x >= {threshold}) and (not flag)"),
            ("threshold_shift", f"(x >= {threshold + 1}) and flag"),
        ]
    elif family == "range_and_flag":
        low = _param(rule, "low")
        high = _param(rule, "high")
        mutants = [
            ("lower_boundary", f"(x > {low}) and (x <= {high}) and flag"),
            ("upper_boundary", f"(x >= {low}) and (x < {high}) and flag"),
            ("join", f"((x >= {low}) and (x <= {high})) or flag"),
            ("negate_flag", f"(x >= {low}) and (x <= {high}) and (not flag)"),
        ]
    elif family == "dual_and":
        x_threshold = _param(rule, "x_threshold")
        y_threshold = _param(rule, "y_threshold")
        mutants = [
            ("x_boundary", f"(x > {x_threshold}) and (y >= {y_threshold})"),
            ("y_boundary", f"(x >= {x_threshold}) and (y > {y_threshold})"),
            ("join", f"(x >= {x_threshold}) or (y >= {y_threshold})"),
            ("x_shift", f"(x >= {x_threshold + 1}) and (y >= {y_threshold})"),
        ]
    elif family == "dual_or":
        x_threshold = _param(rule, "x_threshold")
        y_threshold = _param(rule, "y_threshold")
        mutants = [
            ("x_boundary", f"(x > {x_threshold}) or (y >= {y_threshold})"),
            ("y_boundary", f"(x >= {x_threshold}) or (y > {y_threshold})"),
            ("join", f"(x >= {x_threshold}) and (y >= {y_threshold})"),
            ("y_shift", f"(x >= {x_threshold}) or (y >= {y_threshold + 1})"),
        ]
    elif family == "not_blocked_threshold":
        max_x = _param(rule, "max_x")
        mutants = [
            ("boundary", f"(x < {max_x}) and (not blocked)"),
            ("blocked_positive", f"(x <= {max_x}) and blocked"),
            ("join", f"(x <= {max_x}) or (not blocked)"),
            ("threshold_shift", f"(x <= {max_x - 1}) and (not blocked)"),
        ]
    elif family == "two_bool_and":
        mutants = [
            ("join", "a or b"),
            ("negate_a", "(not a) and b"),
            ("negate_b", "a and (not b)"),
            ("negate_result", "not (a and b)"),
        ]
    elif family == "two_bool_or":
        mutants = [
            ("join", "a and b"),
            ("negate_a", "(not a) or b"),
            ("negate_b", "a or (not b)"),
            ("negate_result", "not (a or b)"),
        ]
    elif family == "tiered_threshold":
        premium_threshold = _param(rule, "premium_threshold")
        standard_threshold = _param(rule, "standard_threshold")
        mutants = [
            (
                "premium_boundary",
                f"(premium and (x > {premium_threshold})) or "
                f"((not premium) and (x >= {standard_threshold}))",
            ),
            (
                "standard_boundary",
                f"(premium and (x >= {premium_threshold})) or "
                f"((not premium) and (x > {standard_threshold}))",
            ),
            (
                "swap_thresholds",
                f"(premium and (x >= {standard_threshold})) or "
                f"((not premium) and (x >= {premium_threshold}))",
            ),
            (
                "join",
                f"(premium and (x >= {premium_threshold})) and "
                f"((not premium) and (x >= {standard_threshold}))",
            ),
        ]
    elif family == "conditional_flag":
        threshold = _param(rule, "threshold")
        mutants = [
            (
                "boundary",
                f"((x > {threshold}) and flag) or ((x <= {threshold}) and fallback)",
            ),
            (
                "negate_flag",
                f"((x >= {threshold}) and (not flag)) or ((x < {threshold}) and fallback)",
            ),
            (
                "negate_fallback",
                f"((x >= {threshold}) and flag) or ((x < {threshold}) and (not fallback))",
            ),
            (
                "join",
                f"((x >= {threshold}) and flag) and ((x < {threshold}) and fallback)",
            ),
        ]
    else:
        raise ValueError(f"unsupported family: {family}")

    return [("correct", correct), *mutants]


def _input_domain(spec: Mapping[str, Any]) -> Iterable[Any]:
    type_name = spec.get("type")
    if type_name == "bool":
        return (False, True)
    if type_name == "int":
        minimum = spec.get("min")
        maximum = spec.get("max")
        if not isinstance(minimum, int) or not isinstance(maximum, int):
            raise ValueError("integer inputs require min and max")
        return range(minimum, maximum + 1)
    raise ValueError(f"unsupported input type: {type_name}")


def assignments(rule: Rule) -> Iterable[dict[str, Any]]:
    inputs = rule.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError(f"rule {rule.get('id')} has invalid inputs")
    names = list(inputs)
    domains = [_input_domain(inputs[name]) for name in names]
    for values in itertools.product(*domains):
        yield dict(zip(names, values, strict=True))


def oracle(rule: Rule, values: Mapping[str, Any]) -> bool:
    family = str(rule["family"])

    if family == "threshold_or_flag":
        return bool(values["x"] >= _param(rule, "threshold") or values["flag"])
    if family == "threshold_and_flag":
        return bool(values["x"] >= _param(rule, "threshold") and values["flag"])
    if family == "range_and_flag":
        return bool(
            values["x"] >= _param(rule, "low")
            and values["x"] <= _param(rule, "high")
            and values["flag"]
        )
    if family == "dual_and":
        return bool(
            values["x"] >= _param(rule, "x_threshold")
            and values["y"] >= _param(rule, "y_threshold")
        )
    if family == "dual_or":
        return bool(
            values["x"] >= _param(rule, "x_threshold") or values["y"] >= _param(rule, "y_threshold")
        )
    if family == "not_blocked_threshold":
        return bool(values["x"] <= _param(rule, "max_x") and not values["blocked"])
    if family == "two_bool_and":
        return bool(values["a"] and values["b"])
    if family == "two_bool_or":
        return bool(values["a"] or values["b"])
    if family == "tiered_threshold":
        if values["premium"]:
            return bool(values["x"] >= _param(rule, "premium_threshold"))
        return bool(values["x"] >= _param(rule, "standard_threshold"))
    if family == "conditional_flag":
        if values["x"] >= _param(rule, "threshold"):
            return bool(values["flag"])
        return bool(values["fallback"])

    raise ValueError(f"unsupported family: {family}")


def expression_matches_oracle(rule: Rule, expression: str) -> bool:
    compiled = compile(expression, "<bizproof-business-benchmark>", "eval")
    for values in assignments(rule):
        observed = bool(eval(compiled, {"__builtins__": {}}, dict(values)))
        if observed != oracle(rule, values):
            return False
    return True


def _input_specs(rule: Rule) -> tuple[InputSpec, ...]:
    inputs = rule.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("invalid inputs")

    specs: list[InputSpec] = []
    for name, raw_spec in inputs.items():
        if not isinstance(raw_spec, dict):
            raise ValueError(f"invalid input spec for {name}")
        type_name = raw_spec.get("type")
        if type_name not in {"int", "bool"}:
            raise ValueError(f"unsupported type for {name}: {type_name}")
        minimum = raw_spec.get("min") if type_name == "int" else None
        maximum = raw_spec.get("max") if type_name == "int" else None
        label = raw_spec.get("label")
        specs.append(
            InputSpec(
                name=str(name),
                type_name=str(type_name),
                minimum=minimum if isinstance(minimum, int) else None,
                maximum=maximum if isinstance(maximum, int) else None,
                label=label if isinstance(label, str) else None,
            )
        )
    return tuple(specs)


def _write_rule_source(path: Path, rule: Rule, expression: str) -> None:
    inputs = rule.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("invalid inputs")
    parts: list[str] = []
    for name, raw_spec in inputs.items():
        if not isinstance(raw_spec, dict):
            raise ValueError("invalid input spec")
        type_name = raw_spec.get("type")
        annotation = "int" if type_name == "int" else "bool"
        parts.append(f"{name}: {annotation}")
    source = f"def target({', '.join(parts)}) -> bool:\n    return {expression}\n"
    path.write_text(source, encoding="utf-8")


def _concrete_matches_oracle(rule: Rule, source: Path) -> bool:
    target = load_function(source, "target")
    for values in assignments(rule):
        observed = bool(target(**values))
        if observed != oracle(rule, values):
            return False
    return True


def _new_bucket() -> dict[str, int]:
    return {
        "cases": 0,
        "expected_proved": 0,
        "expected_disproved": 0,
        "z3_proved": 0,
        "z3_disproved": 0,
        "z3_unknown": 0,
        "disagreements": 0,
    }


def run_benchmark(
    catalog_path: Path,
    output_path: Path,
    *,
    max_rules: int | None = None,
    mutants_per_rule: int = 4,
) -> dict[str, Any]:
    from .enum_backend import verify_by_enumeration
    from .z3_backend import verify_with_z3

    if mutants_per_rule < 1 or mutants_per_rule > 4:
        raise ValueError("mutants_per_rule must be between 1 and 4")

    catalog = load_catalog(catalog_path)
    validate_catalog(catalog)
    raw_rules = catalog["rules"]
    assert isinstance(raw_rules, list)
    rules = raw_rules[:max_rules] if max_rules is not None else raw_rules

    started = time.perf_counter()
    cases_checked = 0
    correct_cases = 0
    mutant_cases = 0
    expected_proved = 0
    expected_disproved = 0
    oracle_label_mismatches = 0
    verdict_disagreements = 0
    enum_false_proved = 0
    enum_false_disproved = 0
    z3_false_proved = 0
    z3_false_disproved = 0
    enum_unknowns = 0
    z3_unknowns = 0
    invalid_replays = 0
    missing_counterexamples = 0
    crashes = 0
    z3_mutants_killed = 0

    per_domain: dict[str, dict[str, int]] = defaultdict(_new_bucket)
    per_family: dict[str, dict[str, int]] = defaultdict(_new_bucket)

    with tempfile.TemporaryDirectory(prefix="bizproof-v03-") as tmp:
        workspace = Path(tmp)

        for raw_rule in rules:
            if not isinstance(raw_rule, dict):
                raise ValueError("invalid rule")
            rule: Rule = raw_rule
            variants = implementation_variants(rule)
            selected = [variants[0], *variants[1 : mutants_per_rule + 1]]

            for variant_name, expression in selected:
                cases_checked += 1
                is_correct_variant = variant_name == "correct"
                if is_correct_variant:
                    correct_cases += 1
                else:
                    mutant_cases += 1

                source = workspace / f"{rule['id']}_{variant_name}.py"
                _write_rule_source(source, rule, expression)

                try:
                    concrete_match = _concrete_matches_oracle(rule, source)
                    expected = Verdict.PROVED if concrete_match else Verdict.DISPROVED
                    declared = Verdict.PROVED if is_correct_variant else Verdict.DISPROVED
                    if expected is not declared:
                        oracle_label_mismatches += 1

                    if expected is Verdict.PROVED:
                        expected_proved += 1
                    else:
                        expected_disproved += 1

                    business_text = rule.get("business_text")
                    contract = BusinessContract(
                        contract_id=f"{rule['id']}::{variant_name}",
                        title=str(rule.get("title", rule["id"])),
                        target=TargetSpec(source=source, function="target"),
                        inputs=_input_specs(rule),
                        precondition="True",
                        postcondition=f"result == ({reference_expression(rule)})",
                        expected_outcome=(
                            str(business_text) if isinstance(business_text, str) else None
                        ),
                    )

                    enum_evidence = verify_by_enumeration(contract)
                    z3_evidence = verify_with_z3(contract)

                    domain = str(rule["domain"])
                    family = str(rule["family"])
                    for bucket in (per_domain[domain], per_family[family]):
                        bucket["cases"] += 1
                        if expected is Verdict.PROVED:
                            bucket["expected_proved"] += 1
                        else:
                            bucket["expected_disproved"] += 1
                        if z3_evidence.verdict is Verdict.PROVED:
                            bucket["z3_proved"] += 1
                        elif z3_evidence.verdict is Verdict.DISPROVED:
                            bucket["z3_disproved"] += 1
                        else:
                            bucket["z3_unknown"] += 1
                        if enum_evidence.verdict is not z3_evidence.verdict:
                            bucket["disagreements"] += 1

                    if enum_evidence.verdict is not z3_evidence.verdict:
                        verdict_disagreements += 1

                    if enum_evidence.verdict is Verdict.UNKNOWN:
                        enum_unknowns += 1
                    if z3_evidence.verdict is Verdict.UNKNOWN:
                        z3_unknowns += 1

                    if expected is Verdict.DISPROVED:
                        if enum_evidence.verdict is Verdict.PROVED:
                            enum_false_proved += 1
                        if z3_evidence.verdict is Verdict.PROVED:
                            z3_false_proved += 1
                        if z3_evidence.verdict is Verdict.DISPROVED:
                            z3_mutants_killed += 1
                            if not z3_evidence.counterexample:
                                missing_counterexamples += 1
                            if z3_evidence.replay_validated is not True:
                                invalid_replays += 1
                    else:
                        if enum_evidence.verdict is Verdict.DISPROVED:
                            enum_false_disproved += 1
                        if z3_evidence.verdict is Verdict.DISPROVED:
                            z3_false_disproved += 1

                except Exception:
                    crashes += 1

    runtime_seconds = time.perf_counter() - started
    non_unknown_z3 = cases_checked - z3_unknowns
    mutation_kill_rate = z3_mutants_killed / mutant_cases if mutant_cases else 0.0
    proof_coverage = non_unknown_z3 / cases_checked if cases_checked else 0.0
    counterexample_coverage = (
        (z3_mutants_killed - missing_counterexamples - invalid_replays) / mutant_cases
        if mutant_cases
        else 0.0
    )

    passed = (
        all(
            value == 0
            for value in (
                oracle_label_mismatches,
                verdict_disagreements,
                enum_false_proved,
                enum_false_disproved,
                z3_false_proved,
                z3_false_disproved,
                enum_unknowns,
                z3_unknowns,
                invalid_replays,
                missing_counterexamples,
                crashes,
            )
        )
        and z3_mutants_killed == mutant_cases
    )

    summary: dict[str, Any] = {
        "benchmark_version": "0.3.0",
        "catalog": str(catalog_path),
        "rules_checked": len(rules),
        "cases_checked": cases_checked,
        "correct_cases": correct_cases,
        "mutant_cases": mutant_cases,
        "expected_proved": expected_proved,
        "expected_disproved": expected_disproved,
        "oracle_label_mismatches": oracle_label_mismatches,
        "enum_z3_verdict_disagreements": verdict_disagreements,
        "enum_false_proved": enum_false_proved,
        "enum_false_disproved": enum_false_disproved,
        "z3_false_proved": z3_false_proved,
        "z3_false_disproved": z3_false_disproved,
        "enum_unknowns": enum_unknowns,
        "z3_unknowns": z3_unknowns,
        "invalid_replays": invalid_replays,
        "missing_counterexamples": missing_counterexamples,
        "unexpected_crashes": crashes,
        "z3_mutants_killed": z3_mutants_killed,
        "mutation_kill_rate": mutation_kill_rate,
        "proof_coverage": proof_coverage,
        "counterexample_coverage": counterexample_coverage,
        "runtime_seconds": runtime_seconds,
        "per_domain": dict(sorted(per_domain.items())),
        "per_family": dict(sorted(per_family.items())),
        "passed": passed,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def _print_summary(summary: Mapping[str, Any]) -> None:
    print("Independent business validation benchmark")
    print(f"Rules checked: {summary['rules_checked']}")
    print(f"Cases checked: {summary['cases_checked']}")
    print(f"Correct implementations: {summary['correct_cases']}")
    print(f"Semantic mutants: {summary['mutant_cases']}")
    print(f"Expected PROVED: {summary['expected_proved']}")
    print(f"Expected DISPROVED: {summary['expected_disproved']}")
    print(f"Oracle label mismatches: {summary['oracle_label_mismatches']}")
    print(f"Enum/Z3 verdict disagreements: {summary['enum_z3_verdict_disagreements']}")
    print(f"Z3 false PROVED: {summary['z3_false_proved']}")
    print(f"Z3 false DISPROVED: {summary['z3_false_disproved']}")
    print(f"Z3 UNKNOWN: {summary['z3_unknowns']}")
    print(f"Invalid replayed counterexamples: {summary['invalid_replays']}")
    print(f"Missing counterexamples: {summary['missing_counterexamples']}")
    print(f"Unexpected crashes: {summary['unexpected_crashes']}")
    print(f"Mutation kill rate: {summary['mutation_kill_rate']:.6f}")
    print(f"Proof coverage: {summary['proof_coverage']:.6f}")
    print(f"Counterexample coverage: {summary['counterexample_coverage']:.6f}")
    print(f"Runtime seconds: {summary['runtime_seconds']:.3f}")
    print("PASS" if summary["passed"] else "FAIL")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the BIZPROOF V0.3 business benchmark")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("benchmarks/v0.3/catalog.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/results/v0.3-business-benchmark-summary.json"),
    )
    parser.add_argument("--max-rules", type=int, default=None)
    parser.add_argument("--mutants-per-rule", type=int, default=4)
    args = parser.parse_args()

    summary = run_benchmark(
        args.catalog,
        args.output,
        max_rules=args.max_rules,
        mutants_per_rule=args.mutants_per_rule,
    )
    _print_summary(summary)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
