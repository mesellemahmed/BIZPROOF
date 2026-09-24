from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .contracts import ContractError, load_contract
from .enum_backend import verify_by_enumeration
from .model import Verdict
from .reporting import render_json, render_text


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bizproof")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--contract", required=True)
    verify.add_argument("--backend", choices=("enum", "z3"), default="z3")
    verify.add_argument("--format", choices=("text", "json"), default="text")
    verify.add_argument("--max-cases", type=int, default=100_000)
    verify.add_argument("--timeout-ms", type=int, default=10_000)

    differential = subparsers.add_parser("differential")
    differential.add_argument(
        "--contracts-dir",
        default="contracts/differential",
    )

    fuzz = subparsers.add_parser("fuzz-differential")
    fuzz.add_argument("--cases", type=int, default=1000)
    fuzz.add_argument("--seed", type=int, default=20260923)
    fuzz.add_argument("--timeout-ms", type=int, default=10000)
    fuzz.add_argument(
        "--generated-dir",
        default="experiments/generated/v0.2",
    )
    fuzz.add_argument(
        "--report",
        default="experiments/results/v0.2-differential-summary.json",
    )

    return parser


def _run_verify(args: argparse.Namespace) -> int:
    try:
        contract = load_contract(args.contract)
    except ContractError as exc:
        print(f"contract error: {exc}", file=sys.stderr)
        return 2

    if args.backend == "enum":
        evidence = verify_by_enumeration(contract, max_cases=args.max_cases)
    else:
        from .z3_backend import verify_with_z3

        evidence = verify_with_z3(contract, timeout_ms=args.timeout_ms)

    output = (
        render_json(contract, evidence)
        if args.format == "json"
        else render_text(contract, evidence)
    )
    print(output)

    if evidence.verdict is Verdict.PROVED:
        return 0
    if evidence.verdict is Verdict.DISPROVED:
        return 1
    return 2


def _run_differential(args: argparse.Namespace) -> int:
    from .differential import run_differential_suite

    summary = run_differential_suite(Path(args.contracts_dir))
    print("Differential verification")
    print(f"Contracts checked: {summary.contracts_checked}")
    print(f"Enum/Z3 verdict disagreements: {summary.verdict_disagreements}")
    print(f"Invalid Z3 counterexamples after concrete replay: {summary.invalid_replays}")
    print(f"Unexpected UNKNOWN verdicts: {summary.unexpected_unknowns}")
    print("PASS" if summary.passed else "FAIL")
    return 0 if summary.passed else 1


def _run_fuzz_differential(args: argparse.Namespace) -> int:
    from .fuzzing import run_fuzz_differential, write_summary

    summary = run_fuzz_differential(
        Path(args.generated_dir),
        cases=args.cases,
        seed=args.seed,
        timeout_ms=args.timeout_ms,
    )
    write_summary(summary, Path(args.report))

    print("Differential semantic fuzzing")
    print(f"Seed: {summary.seed}")
    print(f"Cases checked: {summary.cases_checked}")
    print(f"Expected PROVED: {summary.expected_proved}")
    print(f"Expected DISPROVED: {summary.expected_disproved}")
    print(f"Oracle label mismatches: {summary.oracle_label_mismatches}")
    print(f"Enum/Z3 verdict disagreements: {summary.verdict_disagreements}")
    print(f"False PROVED: {summary.false_proved}")
    print(f"False DISPROVED: {summary.false_disproved}")
    print(f"Enum UNKNOWN: {summary.enum_unknowns}")
    print(f"Z3 UNKNOWN: {summary.z3_unknowns}")
    print(f"Invalid replayed counterexamples: {summary.invalid_replays}")
    print(f"Unexpected crashes: {summary.crashes}")
    print(f"Runtime seconds: {summary.runtime_seconds:.3f}")
    print("PASS" if summary.passed else "FAIL")
    return 0 if summary.passed else 1


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "verify":
        return _run_verify(args)
    if args.command == "differential":
        return _run_differential(args)
    if args.command == "fuzz-differential":
        return _run_fuzz_differential(args)

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
