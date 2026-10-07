from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .contracts import load_contract
from .model import Evidence, Verdict
from .z3_backend import verify_with_z3

JsonDict = dict[str, Any]


def _read_json(path: Path) -> JsonDict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _line_numbers(text: str, anchors: list[str]) -> dict[str, int]:
    lines = text.splitlines()
    found: dict[str, int] = {}

    for anchor in anchors:
        matches = [index for index, line in enumerate(lines, start=1) if anchor in line]
        if not matches:
            raise ValueError(f"anchor not found: {anchor!r}")
        found[anchor] = matches[0]

    return found


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{field} must be a non-empty string list")
    return list(value)


def _verify_provenance(
    rule: JsonDict,
    *,
    lock_by_id: dict[str, JsonDict],
    external_root: Path,
) -> JsonDict:
    source_id = str(rule["source_id"])
    locked = lock_by_id.get(source_id)

    if locked is None:
        raise ValueError(f"external source is not locked: {source_id}")

    expected_commit = str(rule["resolved_commit"])
    locked_commit = str(locked.get("resolved_commit", ""))

    if locked_commit != expected_commit:
        raise ValueError(
            f"commit mismatch for {source_id}: catalog={expected_commit} lock={locked_commit}"
        )

    repository_root = external_root / source_id
    source_path = repository_root / str(rule["external_source"])
    evidence_path = repository_root / str(rule["evidence_file"])

    if not source_path.is_file():
        raise ValueError(f"external source file missing: {source_path}")
    if not evidence_path.is_file():
        raise ValueError(f"external evidence file missing: {evidence_path}")

    source_text = source_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )
    evidence_text = evidence_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    source_anchors = _string_list(
        rule.get("source_anchors"),
        "source_anchors",
    )
    evidence_anchors = _string_list(
        rule.get("evidence_anchors"),
        "evidence_anchors",
    )

    return {
        "source_id": source_id,
        "resolved_commit": expected_commit,
        "external_source": str(rule["external_source"]),
        "external_symbol": str(rule["external_symbol"]),
        "external_source_sha256": _sha256(source_path),
        "source_anchor_lines": _line_numbers(
            source_text,
            source_anchors,
        ),
        "evidence_file": str(rule["evidence_file"]),
        "evidence_sha256": _sha256(evidence_path),
        "evidence_anchor_lines": _line_numbers(
            evidence_text,
            evidence_anchors,
        ),
    }


def _evidence_to_json(evidence: Evidence) -> JsonDict:
    return {
        "verdict": evidence.verdict.value,
        "contract_id": evidence.contract_id,
        "backend": evidence.backend,
        "counterexample": evidence.counterexample,
        "observed_result": evidence.observed_result,
        "postcondition_satisfied": evidence.postcondition_satisfied,
        "replay_validated": evidence.replay_validated,
        "reason_code": evidence.reason_code,
        "reason": evidence.reason,
        "metadata": evidence.metadata,
    }


def _adapter_loc(repo_root: Path, relative: str) -> int:
    text = (repo_root / relative).read_text(encoding="utf-8")
    return sum(
        1 for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
    )


def run_external_semantic_validation(
    *,
    catalog_path: Path,
    lock_path: Path,
    external_root: Path,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:
    catalog = _read_json(catalog_path)
    lock = _read_json(lock_path)

    rules = catalog.get("rules")
    locked_sources = lock.get("sources")

    if not isinstance(rules, list) or not rules:
        raise ValueError("catalog requires a non-empty rules list")
    if not isinstance(locked_sources, list):
        raise ValueError("lock requires a sources list")

    lock_by_id: dict[str, JsonDict] = {}
    for raw in locked_sources:
        if isinstance(raw, dict) and "id" in raw:
            lock_by_id[str(raw["id"])] = raw

    started = time.perf_counter()
    details: list[JsonDict] = []
    correct_counts: Counter[str] = Counter()
    mutant_counts: Counter[str] = Counter()
    scope_counts: Counter[str] = Counter()
    systems: set[str] = set()
    invalid_mutant_replays = 0
    provenance_failures: list[JsonDict] = []

    for raw_rule in rules:
        if not isinstance(raw_rule, dict):
            raise ValueError("every rule must be an object")

        rule = raw_rule
        rule_id = str(rule["id"])
        systems.add(str(rule["source_id"]))
        scope_counts[str(rule["adaptation_scope"])] += 1

        try:
            provenance = _verify_provenance(
                rule,
                lock_by_id=lock_by_id,
                external_root=external_root,
            )
        except (OSError, ValueError) as exc:
            provenance_failures.append(
                {
                    "rule_id": rule_id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        correct_contract_path = repo_root / str(rule["correct_contract"])
        mutant_contract_path = repo_root / str(rule["mutant_contract"])

        correct_contract = load_contract(correct_contract_path)
        mutant_contract = load_contract(mutant_contract_path)

        correct_evidence = verify_with_z3(correct_contract)
        mutant_evidence = verify_with_z3(mutant_contract)

        correct_counts[correct_evidence.verdict.value] += 1
        mutant_counts[mutant_evidence.verdict.value] += 1

        if (
            mutant_evidence.verdict == Verdict.DISPROVED
            and mutant_evidence.replay_validated is not True
        ):
            invalid_mutant_replays += 1

        expected_correct = str(rule["expected_correct_verdict"])
        expected_mutant = str(rule["expected_mutant_verdict"])

        adapter_relative = str(rule["adapter"])

        details.append(
            {
                "rule_id": rule_id,
                "domain": str(rule["domain"]),
                "provenance": provenance,
                "adaptation_scope": str(rule["adaptation_scope"]),
                "adapter_operations": rule["adapter_operations"],
                "representation_change": str(rule["representation_change"]),
                "adapter": adapter_relative,
                "adapter_loc": _adapter_loc(
                    repo_root,
                    adapter_relative,
                ),
                "correct": _evidence_to_json(correct_evidence),
                "mutant": _evidence_to_json(mutant_evidence),
                "expected_correct_verdict": expected_correct,
                "expected_mutant_verdict": expected_mutant,
                "correct_expectation_met": (correct_evidence.verdict.value == expected_correct),
                "mutant_expectation_met": (mutant_evidence.verdict.value == expected_mutant),
            }
        )

    rules_checked = len(details)
    correct_proved = correct_counts[Verdict.PROVED.value]
    mutant_disproved = mutant_counts[Verdict.DISPROVED.value]

    passed = (
        not provenance_failures
        and rules_checked == len(rules)
        and correct_proved == len(rules)
        and mutant_disproved == len(rules)
        and correct_counts[Verdict.UNKNOWN.value] == 0
        and mutant_counts[Verdict.UNKNOWN.value] == 0
        and invalid_mutant_replays == 0
        and all(
            item["correct_expectation_met"] and item["mutant_expectation_met"] for item in details
        )
    )

    summary: JsonDict = {
        "benchmark_version": "0.7.0",
        "claim_scope": catalog["claim_scope"],
        "external_systems": sorted(systems),
        "external_system_count": len(systems),
        "rules_configured": len(rules),
        "rules_checked": rules_checked,
        "correct_adapter_verdicts": dict(sorted(correct_counts.items())),
        "correct_adapters_proved": correct_proved,
        "mutant_verdicts": dict(sorted(mutant_counts.items())),
        "mutants_disproved": mutant_disproved,
        "invalid_mutant_replays": invalid_mutant_replays,
        "provenance_failures": provenance_failures,
        "adaptation_scope_counts": dict(sorted(scope_counts.items())),
        "runtime_seconds": time.perf_counter() - started,
        "passed": passed,
        "interpretation": {
            "proved": (
                "formal proof of the tracked scalar adapter against "
                "the tracked contract over its declared input domain"
            ),
            "not_claimed": (
                "no end-to-end proof of the original external framework "
                "function or its object/database aggregation machinery"
            ),
            "mutants": (
                "secondary sensitivity check only; injected mutants are not external defects"
            ),
        },
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


def _print_summary(summary: JsonDict) -> None:
    print("BIZPROOF V0.7 external semantic validation")
    print(f"External systems: {summary['external_system_count']}")
    print(f"Rules checked: {summary['rules_checked']}")
    print(
        "Correct adapters proved: "
        f"{summary['correct_adapters_proved']}/"
        f"{summary['rules_configured']}"
    )
    print(
        f"Injected mutants disproved: {summary['mutants_disproved']}/{summary['rules_configured']}"
    )
    print(f"Invalid mutant replays: {summary['invalid_mutant_replays']}")
    print(f"Provenance failures: {len(summary['provenance_failures'])}")
    print(f"Runtime seconds: {summary['runtime_seconds']:.6f}")
    print("PASS" if summary["passed"] else "FAIL")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate tracked scalar adapters derived from locked "
            "external business-rule implementations."
        )
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("benchmarks/v0.7/catalog.json"),
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
        default=Path("benchmarks/v0.7/results"),
    )
    args = parser.parse_args()

    summary = run_external_semantic_validation(
        catalog_path=args.catalog,
        lock_path=args.lock,
        external_root=args.external_root,
        repo_root=args.repo_root,
        output_dir=args.output_dir,
    )
    _print_summary(summary)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
