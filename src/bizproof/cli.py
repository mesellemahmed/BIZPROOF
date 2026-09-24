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


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "verify":
        return _run_verify(args)
    if args.command == "differential":
        return _run_differential(args)

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
