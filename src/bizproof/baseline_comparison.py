from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import tempfile
import time
from collections import defaultdict
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path
from typing import Any

from hypothesis import Phase, find, settings
from hypothesis import strategies as st
from hypothesis.errors import NoSuchExample

from .business_benchmark import (
    implementation_variants,
    load_catalog,
    oracle,
    reference_expression,
    validate_catalog,
)
from .loader import load_function
from .model import BusinessContract, InputSpec, TargetSpec, Verdict
from .z3_backend import verify_with_z3

Rule = dict[str, Any]


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


def _write_candidate_source(path: Path, rule: Rule, expression: str) -> None:
    signature, _ = _function_signature(rule)
    source = f"def target({signature}) -> bool:\n    return {expression}\n"
    path.write_text(source, encoding="utf-8")


def _domain_assertions(rule: Rule) -> list[str]:
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
                raise ValueError(f"integer input {name} requires min and max")
            assertions.append(f"    assert {name} >= {minimum}")
            assertions.append(f"    assert {name} <= {maximum}")
    return assertions


def _write_crosshair_source(path: Path, rule: Rule, expression: str) -> None:
    signature, names = _function_signature(rule)
    arguments = ", ".join(names)
    preconditions = _domain_assertions(rule)
    if not preconditions:
        preconditions = ["    assert True"]

    lines = [
        f"def target({signature}) -> bool:",
        f"    return {expression}",
        "",
        f"def check_business_rule({signature}) -> None:",
        *preconditions,
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
                raise ValueError(f"integer input {name} requires min and max")
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
            lambda values: bool(target(**values)) != oracle(rule, values),
            settings=hypothesis_settings,
        )
        return True, dict(witness), time.perf_counter() - started, None
    except NoSuchExample:
        return False, None, time.perf_counter() - started, None
    except Exception as exc:
        return None, None, time.perf_counter() - started, f"{type(exc).__name__}: {exc}"


def _run_crosshair(
    source: Path,
    *,
    per_condition_timeout: float,
    process_timeout: float,
) -> tuple[bool | None, float, str | None]:
    started = time.perf_counter()
    command = [
        "crosshair",
        "check",
        "--analysis_kind=asserts",
        f"--per_condition_timeout={per_condition_timeout}",
        str(source),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=process_timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, time.perf_counter() - started, "process_timeout"
    except OSError as exc:
        return None, time.perf_counter() - started, f"{type(exc).__name__}: {exc}"

    elapsed = time.perf_counter() - started
    if result.returncode == 1:
        return True, elapsed, None
    if result.returncode == 0:
        return False, elapsed, None

    detail = (result.stderr or result.stdout).strip()
    return None, elapsed, detail or f"crosshair_exit_{result.returncode}"


def _new_method_summary() -> dict[str, Any]:
    return {
        "cases": 0,
        "mutants": 0,
        "correct_cases": 0,
        "mutants_detected": 0,
        "correct_false_alarms": 0,
        "no_counterexample_on_correct": 0,
        "missed_mutants": 0,
        "unknown_or_error": 0,
        "runtime_seconds": 0.0,
    }


def _record_detection(
    summary: dict[str, Any],
    *,
    expected_disproved: bool,
    detected: bool | None,
    runtime_seconds: float,
) -> None:
    summary["cases"] += 1
    summary["runtime_seconds"] += runtime_seconds
    if expected_disproved:
        summary["mutants"] += 1
        if detected is True:
            summary["mutants_detected"] += 1
        elif detected is False:
            summary["missed_mutants"] += 1
        else:
            summary["unknown_or_error"] += 1
    else:
        summary["correct_cases"] += 1
        if detected is True:
            summary["correct_false_alarms"] += 1
        elif detected is False:
            summary["no_counterexample_on_correct"] += 1
        else:
            summary["unknown_or_error"] += 1


def _finalize_method(
    summary: dict[str, Any],
    *,
    method_name: str,
) -> dict[str, Any]:
    mutants = int(summary["mutants"])
    correct_cases = int(summary["correct_cases"])
    cases = int(summary["cases"])

    summary["mutant_detection_rate"] = summary["mutants_detected"] / mutants if mutants else 0.0
    summary["correct_false_alarm_rate"] = (
        summary["correct_false_alarms"] / correct_cases if correct_cases else 0.0
    )

    proof_capable = method_name == "bizproof"
    summary["proof_capable"] = proof_capable

    if proof_capable:
        summary["correct_cases_proved"] = summary["no_counterexample_on_correct"]
        summary["correct_cases_inconclusive"] = 0
    else:
        summary["correct_cases_proved"] = 0
        summary["correct_cases_inconclusive"] = summary["no_counterexample_on_correct"]

    summary["proof_rate_on_correct"] = (
        summary["correct_cases_proved"] / correct_cases if correct_cases else 0.0
    )
    summary["conclusive_case_rate"] = (
        (
            summary["mutants_detected"]
            + summary["correct_false_alarms"]
            + summary["correct_cases_proved"]
        )
        / cases
        if cases
        else 0.0
    )
    summary["runtime_seconds"] = round(float(summary["runtime_seconds"]), 6)
    return summary


def run_baseline_comparison(
    catalog_path: Path,
    output_path: Path,
    details_path: Path,
    *,
    max_rules: int | None = None,
    mutants_per_rule: int = 4,
    hypothesis_examples: int = 100,
    crosshair_condition_timeout: float = 0.5,
    crosshair_process_timeout: float = 5.0,
) -> dict[str, Any]:
    if mutants_per_rule < 1 or mutants_per_rule > 4:
        raise ValueError("mutants_per_rule must be between 1 and 4")
    if hypothesis_examples < 1:
        raise ValueError("hypothesis_examples must be positive")

    catalog = load_catalog(catalog_path)
    validate_catalog(catalog)
    raw_rules = catalog["rules"]
    if not isinstance(raw_rules, list):
        raise ValueError("catalog rules must be a list")
    rules = raw_rules[:max_rules] if max_rules is not None else raw_rules

    method_summaries = {
        "bizproof": _new_method_summary(),
        "hypothesis": _new_method_summary(),
        "crosshair": _new_method_summary(),
    }
    tool_errors: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    pairwise: dict[str, defaultdict[str, int]] = {
        "bizproof_vs_hypothesis": defaultdict(int),
        "bizproof_vs_crosshair": defaultdict(int),
    }
    per_domain: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: {
            "bizproof": _new_method_summary(),
            "hypothesis": _new_method_summary(),
            "crosshair": _new_method_summary(),
        }
    )

    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="bizproof-v04-") as tmp:
        workspace = Path(tmp)

        for raw_rule in rules:
            if not isinstance(raw_rule, dict):
                raise ValueError("invalid rule")
            rule: Rule = raw_rule
            variants = implementation_variants(rule)
            selected = [variants[0], *variants[1 : mutants_per_rule + 1]]

            for variant_name, expression in selected:
                expected_disproved = variant_name != "correct"
                source = workspace / f"{rule['id']}_{variant_name}.py"
                crosshair_source = workspace / f"{rule['id']}_{variant_name}_crosshair.py"
                _write_candidate_source(source, rule, expression)
                _write_crosshair_source(crosshair_source, rule, expression)

                contract = BusinessContract(
                    contract_id=f"{rule['id']}::{variant_name}",
                    title=str(rule.get("title", rule["id"])),
                    target=TargetSpec(source=source, function="target"),
                    inputs=_input_specs(rule),
                    precondition="True",
                    postcondition=f"result == ({reference_expression(rule)})",
                    expected_outcome=str(rule.get("business_text", "")),
                )

                biz_started = time.perf_counter()
                biz_evidence = verify_with_z3(contract)
                biz_runtime = time.perf_counter() - biz_started
                if biz_evidence.verdict is Verdict.DISPROVED:
                    biz_detected: bool | None = True
                elif biz_evidence.verdict is Verdict.PROVED:
                    biz_detected = False
                else:
                    biz_detected = None

                hyp_detected, hyp_witness, hyp_runtime, hyp_error = _run_hypothesis(
                    rule,
                    source,
                    max_examples=hypothesis_examples,
                )
                cross_detected, cross_runtime, cross_error = _run_crosshair(
                    crosshair_source,
                    per_condition_timeout=crosshair_condition_timeout,
                    process_timeout=crosshair_process_timeout,
                )

                domain = str(rule["domain"])
                for method_name, detected, runtime in (
                    ("bizproof", biz_detected, biz_runtime),
                    ("hypothesis", hyp_detected, hyp_runtime),
                    ("crosshair", cross_detected, cross_runtime),
                ):
                    _record_detection(
                        method_summaries[method_name],
                        expected_disproved=expected_disproved,
                        detected=detected,
                        runtime_seconds=runtime,
                    )
                    _record_detection(
                        per_domain[domain][method_name],
                        expected_disproved=expected_disproved,
                        detected=detected,
                        runtime_seconds=runtime,
                    )

                if hyp_error is not None:
                    tool_errors.append(
                        {
                            "tool": "hypothesis",
                            "case": f"{rule['id']}::{variant_name}",
                            "error": hyp_error,
                        }
                    )
                if cross_error is not None:
                    tool_errors.append(
                        {
                            "tool": "crosshair",
                            "case": f"{rule['id']}::{variant_name}",
                            "error": cross_error,
                        }
                    )

                if expected_disproved:
                    for key, baseline_detection in (
                        ("bizproof_vs_hypothesis", hyp_detected),
                        ("bizproof_vs_crosshair", cross_detected),
                    ):
                        if biz_detected is True and baseline_detection is True:
                            pairwise[key]["both_detected"] += 1
                        elif biz_detected is True and baseline_detection is False:
                            pairwise[key]["bizproof_only"] += 1
                        elif biz_detected is False and baseline_detection is True:
                            pairwise[key]["baseline_only"] += 1
                        elif biz_detected is False and baseline_detection is False:
                            pairwise[key]["neither"] += 1
                        else:
                            pairwise[key]["inconclusive"] += 1

                rows.append(
                    {
                        "rule_id": rule["id"],
                        "domain": domain,
                        "family": rule["family"],
                        "variant": variant_name,
                        "expected": "DISPROVED" if expected_disproved else "PROVED",
                        "bizproof": (
                            "DETECTED"
                            if biz_detected is True
                            else "NO_COUNTEREXAMPLE"
                            if biz_detected is False
                            else "UNKNOWN"
                        ),
                        "hypothesis": (
                            "DETECTED"
                            if hyp_detected is True
                            else "NO_COUNTEREXAMPLE"
                            if hyp_detected is False
                            else "ERROR"
                        ),
                        "crosshair": (
                            "DETECTED"
                            if cross_detected is True
                            else "NO_COUNTEREXAMPLE"
                            if cross_detected is False
                            else "ERROR"
                        ),
                        "bizproof_runtime_seconds": round(biz_runtime, 6),
                        "hypothesis_runtime_seconds": round(hyp_runtime, 6),
                        "crosshair_runtime_seconds": round(cross_runtime, 6),
                        "hypothesis_witness": (
                            json.dumps(hyp_witness, sort_keys=True)
                            if hyp_witness is not None
                            else ""
                        ),
                        "hypothesis_error": hyp_error or "",
                        "crosshair_error": cross_error or "",
                    }
                )

    finalized_methods = {
        name: _finalize_method(summary, method_name=name)
        for name, summary in method_summaries.items()
    }
    finalized_domains = {
        domain: {
            method: _finalize_method(summary, method_name=method)
            for method, summary in methods.items()
        }
        for domain, methods in sorted(per_domain.items())
    }

    biz = finalized_methods["bizproof"]
    passed = (
        not tool_errors
        and biz["missed_mutants"] == 0
        and biz["correct_false_alarms"] == 0
        and biz["unknown_or_error"] == 0
    )

    summary: dict[str, Any] = {
        "benchmark_version": "0.4.1",
        "catalog": str(catalog_path),
        "rules_checked": len(rules),
        "cases_checked": len(rows),
        "mutants_per_rule": mutants_per_rule,
        "hypothesis_max_examples": hypothesis_examples,
        "crosshair_per_condition_timeout": crosshair_condition_timeout,
        "crosshair_process_timeout": crosshair_process_timeout,
        "environment": {
            "python": platform.python_version(),
            "hypothesis": version("hypothesis"),
            "crosshair_tool": version("crosshair-tool"),
        },
        "methods": finalized_methods,
        "per_domain": finalized_domains,
        "pairwise_mutant_detection": {
            name: dict(sorted(counts.items())) for name, counts in pairwise.items()
        },
        "tool_errors": tool_errors,
        "wall_runtime_seconds": round(time.perf_counter() - started, 6),
        "interpretation": {
            "bizproof_no_counterexample": (
                "formal verdict PROVED within the supported BIZPROOF semantics"
            ),
            "hypothesis_no_counterexample": (
                "no counterexample found within the configured search budget; "
                "reported as inconclusive on correct cases, not as a proof"
            ),
            "crosshair_no_counterexample": (
                "no counterexample reported within the configured analysis budget; "
                "reported as inconclusive on correct cases, not as a proof"
            ),
            "classification_accuracy": (
                "not reported for search-based baselines because absence of a "
                "counterexample is not a proof of correctness"
            ),
        },
        "passed": passed,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    details_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with details_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return summary


def _print_method(name: str, summary: Mapping[str, Any]) -> None:
    print(f"{name}:")
    print(f"  mutants detected: {summary['mutants_detected']}/{summary['mutants']}")
    print(f"  mutant detection rate: {summary['mutant_detection_rate']:.6f}")
    print(f"  correct false alarms: {summary['correct_false_alarms']}/{summary['correct_cases']}")
    print(f"  correct cases proved: {summary['correct_cases_proved']}/{summary['correct_cases']}")
    print(
        "  correct cases inconclusive: "
        f"{summary['correct_cases_inconclusive']}/{summary['correct_cases']}"
    )
    print(f"  proof rate on correct: {summary['proof_rate_on_correct']:.6f}")
    print(f"  conclusive case rate: {summary['conclusive_case_rate']:.6f}")
    print(f"  unknown/error: {summary['unknown_or_error']}")
    print(f"  runtime seconds: {summary['runtime_seconds']:.3f}")


def _print_summary(summary: Mapping[str, Any]) -> None:
    print("BIZPROOF baseline comparison")
    print(f"Rules checked: {summary['rules_checked']}")
    print(f"Cases checked: {summary['cases_checked']}")
    methods = summary["methods"]
    if not isinstance(methods, dict):
        raise ValueError("invalid methods summary")
    for name in ("bizproof", "hypothesis", "crosshair"):
        method_summary = methods[name]
        if not isinstance(method_summary, dict):
            raise ValueError(f"invalid summary for {name}")
        _print_method(name, method_summary)
    errors = summary["tool_errors"]
    print(f"Tool errors: {len(errors) if isinstance(errors, list) else 'invalid'}")
    print(f"Wall runtime seconds: {summary['wall_runtime_seconds']:.3f}")
    print("PASS" if summary["passed"] else "FAIL")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare BIZPROOF against testing baselines")
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--details", type=Path, required=True)
    parser.add_argument("--max-rules", type=int)
    parser.add_argument("--mutants-per-rule", type=int, default=4)
    parser.add_argument("--hypothesis-examples", type=int, default=100)
    parser.add_argument("--crosshair-condition-timeout", type=float, default=0.5)
    parser.add_argument("--crosshair-process-timeout", type=float, default=5.0)
    args = parser.parse_args()

    summary = run_baseline_comparison(
        args.catalog,
        args.output,
        args.details,
        max_rules=args.max_rules,
        mutants_per_rule=args.mutants_per_rule,
        hypothesis_examples=args.hypothesis_examples,
        crosshair_condition_timeout=args.crosshair_condition_timeout,
        crosshair_process_timeout=args.crosshair_process_timeout,
    )
    _print_summary(summary)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
