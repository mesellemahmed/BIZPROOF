from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .adapter_preservation import _checkout_commit

JsonDict = dict[str, Any]


def _load_json(path: Path) -> JsonDict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: JsonDict) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: JsonDict) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _detail_map(path: Path) -> dict[str, JsonDict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"expected JSON list: {path}")

    result: dict[str, JsonDict] = {}
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"invalid detail item in {path}")
        rule_id = str(item["rule_id"])
        if rule_id in result:
            raise ValueError(f"duplicate rule id {rule_id} in {path}")
        result[rule_id] = item
    return result


def _require(condition: bool, checks: list[JsonDict], name: str, detail: str) -> None:
    checks.append(
        {
            "name": name,
            "passed": bool(condition),
            "detail": detail,
        }
    )


def _first_failed(checks: list[JsonDict]) -> list[str]:
    return [str(item["name"]) for item in checks if not bool(item["passed"])]


def _reviewer_report(summary: JsonDict, certificates: list[JsonDict]) -> str:
    lines = [
        "# BIZPROOF V0.10 Reviewer Certification Report",
        "",
        "## Scope",
        "",
        str(summary["claim_scope"]),
        "",
        "## Global result",
        "",
        f"- Certificates configured: {summary['certificates_configured']}",
        f"- Certificates issued: {summary['certificates_issued']}",
        f"- Certificates failed: {summary['certificates_failed']}",
        f"- External systems: {summary['external_system_count']}",
        f"- V0.8 concrete comparisons represented: {summary['v08_total_comparisons']}",
        f"- V0.8 correct-adapter mismatches represented: {summary['v08_correct_mismatches']}",
        f"- V0.9 symbolic equivalences represented: {summary['v09_equivalences_proved']}",
        f"- Pipeline result: {'PASS' if summary['passed'] else 'FAIL'}",
        "",
        "## Certificates",
        "",
    ]

    for item in certificates:
        lines.extend(
            [
                f"### {item['certificate_id']}",
                "",
                f"- Status: **{item['status']}**",
                f"- Certification scope: `{item['certification_scope']}`",
                f"- External system: `{item['provenance']['source_id']}`",
                f"- Commit: `{item['provenance']['resolved_commit']}`",
                f"- Source: `{item['provenance']['external_source']}`",
                f"- Adapter: `{item['artifacts']['adapter_path']}`",
                f"- Contract: `{item['artifacts']['contract_path']}`",
                f"- V0.7: `{item['evidence']['v0.7']['correct_verdict']}`",
                (
                    f"- V0.8: {item['evidence']['v0.8']['comparisons']} comparisons, "
                    f"{item['evidence']['v0.8']['correct_mismatches']} correct mismatches"
                ),
                (
                    f"- V0.9: `{item['evidence']['v0.9']['correct_verdict']}` "
                    f"(`{item['evidence']['v0.9']['solver_status']}`)"
                ),
                f"- Certified symbolic slice: `{item['evidence']['v0.9']['external_slice']}`",
                f"- Certificate digest: `{item['certificate_digest']}`",
                "",
            ]
        )

        if item["failed_checks"]:
            lines.append("- Failed checks: " + ", ".join(item["failed_checks"]))
            lines.append("")

    return "\n".join(lines) + "\n"


def run_certification(
    *,
    registry_path: Path,
    lock_path: Path,
    repo_root: Path,
    external_root: Path,
    certificates_dir: Path,
    results_dir: Path,
) -> JsonDict:
    started = time.perf_counter()

    registry = _load_json(registry_path)
    lock = _load_json(lock_path)

    v07_summary = _load_json(repo_root / "benchmarks/v0.7/results/summary.json")
    v08_summary = _load_json(repo_root / "benchmarks/v0.8/results/summary.json")
    v09_summary = _load_json(repo_root / "benchmarks/v0.9/results/summary.json")

    v07 = _detail_map(repo_root / "benchmarks/v0.7/results/details.json")
    v08 = _detail_map(repo_root / "benchmarks/v0.8/results/details.json")
    v09 = _detail_map(repo_root / "benchmarks/v0.9/results/details.json")

    raw_sources = lock.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("LOCK sources must be a list")

    locked = {
        str(item["id"]): str(item["resolved_commit"])
        for item in raw_sources
        if isinstance(item, dict) and "id" in item and "resolved_commit" in item
    }

    raw_rules = registry.get("rules")
    if not isinstance(raw_rules, list):
        raise ValueError("registry rules must be a list")

    certificates_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    certificates: list[JsonDict] = []
    index_items: list[JsonDict] = []

    for raw in raw_rules:
        if not isinstance(raw, dict):
            raise ValueError("registry rule must be an object")

        cert_id = str(raw["certificate_id"])
        source_id = str(raw["source_id"])
        expected_commit = str(raw["resolved_commit"])

        checks: list[JsonDict] = []

        checkout_commit = _checkout_commit(external_root / source_id)
        _require(
            source_id in locked,
            checks,
            "lock-source-present",
            source_id,
        )
        _require(
            locked.get(source_id) == expected_commit,
            checks,
            "registry-lock-commit",
            expected_commit,
        )
        _require(
            checkout_commit == expected_commit,
            checks,
            "checkout-lock-commit",
            checkout_commit,
        )

        external_path = external_root / source_id / str(raw["external_source"])
        adapter_path = repo_root / str(raw["adapter"])
        contract_path = repo_root / str(raw["contract"])

        _require(
            external_path.is_file(),
            checks,
            "external-source-present",
            str(raw["external_source"]),
        )
        _require(
            adapter_path.is_file(),
            checks,
            "adapter-present",
            str(raw["adapter"]),
        )
        _require(
            contract_path.is_file(),
            checks,
            "contract-present",
            str(raw["contract"]),
        )

        v07_id = str(raw["v07_rule_id"])
        v08_id = str(raw["v08_rule_id"])
        v09_id = str(raw["v09_rule_id"])

        _require(v07_id in v07, checks, "v0.7-evidence-present", v07_id)
        _require(v08_id in v08, checks, "v0.8-evidence-present", v08_id)
        _require(v09_id in v09, checks, "v0.9-evidence-present", v09_id)

        if v07_id not in v07 or v08_id not in v08 or v09_id not in v09:
            missing_failed_checks = _first_failed(checks)
            certificate_core: JsonDict = {
                "certificate_version": "0.10.0",
                "certificate_id": cert_id,
                "status": "FAILED",
                "claim_scope": registry["claim_scope"],
                "failed_checks": missing_failed_checks,
                "checks": checks,
            }
            digest = _digest(certificate_core)
            envelope = {
                **certificate_core,
                "certificate_digest": digest,
            }
            certificates.append(envelope)
            index_items.append(
                {
                    "certificate_id": cert_id,
                    "status": "FAILED",
                    "certificate_digest": digest,
                }
            )
            continue

        d07 = v07[v07_id]
        d08 = v08[v08_id]
        d09 = v09[v09_id]

        _require(
            bool(v07_summary.get("passed")),
            checks,
            "v0.7-summary-pass",
            "summary passed",
        )
        _require(
            bool(v08_summary.get("passed")),
            checks,
            "v0.8-summary-pass",
            "summary passed",
        )
        _require(
            bool(v09_summary.get("passed")),
            checks,
            "v0.9-summary-pass",
            "summary passed",
        )

        _require(
            str(d07["correct"]["verdict"]) == "PROVED",
            checks,
            "v0.7-correct-proved",
            str(d07["correct"]["verdict"]),
        )
        _require(
            str(d07["mutant"]["verdict"]) == "DISPROVED",
            checks,
            "v0.7-mutant-disproved",
            str(d07["mutant"]["verdict"]),
        )
        _require(
            bool(d07["mutant"]["replay_validated"]),
            checks,
            "v0.7-mutant-replay",
            str(d07["mutant"]["replay_validated"]),
        )

        _require(
            int(d08["correct_mismatches"]) == 0,
            checks,
            "v0.8-zero-correct-mismatch",
            str(d08["correct_mismatches"]),
        )
        _require(
            int(d08["mutant_mismatches"]) > 0,
            checks,
            "v0.8-mutant-sensitive",
            str(d08["mutant_mismatches"]),
        )
        _require(
            bool(d08["passed"]),
            checks,
            "v0.8-rule-pass",
            str(d08["passed"]),
        )

        _require(
            str(d09["correct"]["verdict"]) == "PROVED",
            checks,
            "v0.9-correct-proved",
            str(d09["correct"]["verdict"]),
        )
        _require(
            str(d09["correct"]["solver_status"]) == "unsat",
            checks,
            "v0.9-correct-unsat",
            str(d09["correct"]["solver_status"]),
        )
        _require(
            str(d09["mutant"]["verdict"]) == "DISPROVED",
            checks,
            "v0.9-mutant-disproved",
            str(d09["mutant"]["verdict"]),
        )
        _require(
            str(d09["mutant"]["solver_status"]) == "sat",
            checks,
            "v0.9-mutant-sat",
            str(d09["mutant"]["solver_status"]),
        )
        _require(
            d09["mutant"]["counterexample"] is not None,
            checks,
            "v0.9-mutant-witness",
            str(d09["mutant"]["counterexample"]),
        )

        external_sha = _sha256_file(external_path)
        adapter_sha = _sha256_file(adapter_path)
        contract_sha = _sha256_file(contract_path)

        _require(
            str(d08["resolved_commit"]) == expected_commit,
            checks,
            "v0.8-commit-consistency",
            str(d08["resolved_commit"]),
        )
        _require(
            str(d09["resolved_commit"]) == expected_commit,
            checks,
            "v0.9-commit-consistency",
            str(d09["resolved_commit"]),
        )
        _require(
            str(d08["external_source_sha256"]) == external_sha,
            checks,
            "v0.8-source-hash",
            external_sha,
        )
        _require(
            str(d09["external_source_sha256"]) == external_sha,
            checks,
            "v0.9-source-hash",
            external_sha,
        )
        _require(
            str(d08["adapter_sha256"]) == adapter_sha,
            checks,
            "v0.8-adapter-hash",
            adapter_sha,
        )
        _require(
            str(d09["adapter_file_sha256"]) == adapter_sha,
            checks,
            "v0.9-adapter-hash",
            adapter_sha,
        )

        status = "CERTIFIED" if all(bool(item["passed"]) for item in checks) else "FAILED"

        certificate_core = {
            "certificate_version": "0.10.0",
            "certificate_id": cert_id,
            "status": status,
            "claim_scope": registry["claim_scope"],
            "certification_scope": str(raw["certification_scope"]),
            "provenance": {
                "source_id": source_id,
                "resolved_commit": expected_commit,
                "external_source": str(raw["external_source"]),
                "external_source_sha256": external_sha,
                "external_class": str(raw["external_class"]),
                "external_method": str(raw["external_method"]),
            },
            "artifacts": {
                "adapter_path": str(raw["adapter"]),
                "adapter_function": str(raw["adapter_function"]),
                "adapter_sha256": adapter_sha,
                "contract_path": str(raw["contract"]),
                "contract_sha256": contract_sha,
            },
            "evidence": {
                "v0.7": {
                    "rule_id": v07_id,
                    "correct_verdict": str(d07["correct"]["verdict"]),
                    "mutant_verdict": str(d07["mutant"]["verdict"]),
                    "mutant_replay_validated": bool(d07["mutant"]["replay_validated"]),
                    "evidence_sha256": _digest(d07),
                },
                "v0.8": {
                    "rule_id": v08_id,
                    "comparisons": int(d08["comparisons"]),
                    "correct_mismatches": int(d08["correct_mismatches"]),
                    "mutant_mismatches": int(d08["mutant_mismatches"]),
                    "evidence_sha256": _digest(d08),
                },
                "v0.9": {
                    "rule_id": v09_id,
                    "external_mode": str(d09["external_mode"]),
                    "external_slice": str(d09["external_slice"]),
                    "correct_verdict": str(d09["correct"]["verdict"]),
                    "solver_status": str(d09["correct"]["solver_status"]),
                    "mutant_verdict": str(d09["mutant"]["verdict"]),
                    "mutant_solver_status": str(d09["mutant"]["solver_status"]),
                    "mutant_counterexample": d09["mutant"]["counterexample"],
                    "external_slice_sha256": str(d09["external_slice_sha256"]),
                    "evidence_sha256": _digest(d09),
                },
            },
            "checks": checks,
            "failed_checks": _first_failed(checks),
        }

        digest = _digest(certificate_core)
        envelope = {
            **certificate_core,
            "certificate_digest": digest,
        }

        certificate_path = certificates_dir / f"{cert_id}.json"
        certificate_path.write_text(
            json.dumps(envelope, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        certificates.append(envelope)
        index_items.append(
            {
                "certificate_id": cert_id,
                "status": status,
                "certificate_digest": digest,
                "path": str(
                    certificate_path.relative_to(repo_root)
                    if certificate_path.is_relative_to(repo_root)
                    else certificate_path
                ),
            }
        )

    issued = sum(1 for item in certificates if item["status"] == "CERTIFIED")
    failed_count = len(certificates) - issued

    summary: JsonDict = {
        "benchmark_version": "0.10.0",
        "claim_scope": registry["claim_scope"],
        "certificates_configured": len(raw_rules),
        "certificates_issued": issued,
        "certificates_failed": failed_count,
        "external_system_count": len(
            {str(item["source_id"]) for item in raw_rules if isinstance(item, dict)}
        ),
        "v08_total_comparisons": sum(
            int(item["evidence"]["v0.8"]["comparisons"])
            for item in certificates
            if item["status"] == "CERTIFIED"
        ),
        "v08_correct_mismatches": sum(
            int(item["evidence"]["v0.8"]["correct_mismatches"])
            for item in certificates
            if item["status"] == "CERTIFIED"
        ),
        "v09_equivalences_proved": sum(
            1
            for item in certificates
            if item["status"] == "CERTIFIED"
            and item["evidence"]["v0.9"]["correct_verdict"] == "PROVED"
        ),
        "runtime_seconds": time.perf_counter() - started,
        "passed": issued == len(raw_rules) and failed_count == 0,
    }

    index = {
        "benchmark_version": "0.10.0",
        "certificates": index_items,
        "index_digest": _digest({"certificates": index_items}),
    }

    (results_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (results_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (results_dir / "REVIEWER_REPORT.md").write_text(
        _reviewer_report(summary, certificates),
        encoding="utf-8",
    )

    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("benchmarks/v0.10/registry.json"),
    )
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path("benchmarks/v0.6/LOCK.json"),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
    )
    parser.add_argument(
        "--external-root",
        type=Path,
        default=Path("external_sources/v0.6"),
    )
    parser.add_argument(
        "--certificates-dir",
        type=Path,
        default=Path("benchmarks/v0.10/certificates"),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("benchmarks/v0.10/results"),
    )
    args = parser.parse_args()

    summary = run_certification(
        registry_path=args.registry,
        lock_path=args.lock,
        repo_root=args.repo_root,
        external_root=args.external_root,
        certificates_dir=args.certificates_dir,
        results_dir=args.results_dir,
    )

    print("BIZPROOF V0.10 evidence-carrying certification pipeline")
    print(
        f"Certificates issued: "
        f"{summary['certificates_issued']}/"
        f"{summary['certificates_configured']}"
    )
    print(f"Failed certificates: {summary['certificates_failed']}")
    print(f"Represented V0.8 comparisons: {summary['v08_total_comparisons']}")
    print(f"Represented V0.9 equivalences: {summary['v09_equivalences_proved']}")
    print(f"Runtime seconds: {summary['runtime_seconds']:.6f}")
    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
