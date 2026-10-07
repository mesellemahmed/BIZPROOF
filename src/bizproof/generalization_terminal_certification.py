from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any, TypeAlias

JsonDict: TypeAlias = dict[str, Any]

TARGET_CANDIDATE = "aab5348ee173d6e3"

CERTIFICATE_ID = "CERT-V011-OSCAR-SHIPPING-001"

EXPECTED_OSCAR_COMMIT = "5699d78449954f047d6d715fd2b6c5d19594e0f3"

COHORT_SHA256 = "3144f973a166ebee41a059c538b81ffac5a5d15737982c6d95e59175325ca108"

TERMINAL_OUTCOMES = {
    "CERTIFIED_A0",
    "CERTIFIED_A1",
    "CERTIFIED_A2",
    "NOT_CERTIFIED_UNKNOWN",
    "NOT_CERTIFIED_UNSUPPORTED",
    "NOT_CERTIFIED_PROVENANCE",
    "NOT_CERTIFIED_EXECUTION",
    "NOT_CERTIFIED_SEMANTIC_AMBIGUITY",
}


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

    values: list[JsonDict] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue

        value = json.loads(raw)

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(f"expected JSON object: {path}")

        values.append(value)

    return values


def _sha256_file(
    path: Path,
) -> str:

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(
    value: str,
) -> str:

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_digest(
    value: JsonDict,
) -> str:

    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=True,
    )

    return _sha256_text(canonical)


def _protocol_levels(
    protocol_path: Path,
) -> JsonDict:

    lines = protocol_path.read_text(encoding="utf-8").splitlines()

    expected_fragments = {
        "CERTIFIED_A0": ("without human semantic mapping or adapter rewriting"),
        "CERTIFIED_A1": ("with declarative source-to-BVC bindings only"),
        "CERTIFIED_A2": ("with an explicit human-authored scalar semantic adapter"),
    }

    result: JsonDict = {}

    for (
        outcome,
        fragment,
    ) in expected_fragments.items():
        matches = [
            {
                "line": index + 1,
                "text": line,
            }
            for (
                index,
                line,
            ) in enumerate(lines)
            if (f"`{outcome}`" in line and fragment in line)
        ]

        if len(matches) != 1:
            raise ValueError(f"protocol definition mismatch for {outcome}: {matches}")

        result[outcome] = matches[0]

    return result


def _classify_certified_level(
    *,
    explicit_scalar_adapter: bool,
    declarative_bindings: bool,
) -> str:

    if explicit_scalar_adapter:
        return "CERTIFIED_A2"

    if declarative_bindings:
        return "CERTIFIED_A1"

    return "CERTIFIED_A0"


def _extract_function(
    path: Path,
    function_name: str,
) -> JsonDict:

    source = path.read_text(encoding="utf-8")

    tree = ast.parse(
        source,
        filename=str(path),
    )

    matches = [
        node
        for node in tree.body
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name == function_name
        )
    ]

    if len(matches) != 1:
        raise ValueError(f"expected one {function_name}; found {len(matches)}")

    node = matches[0]

    segment = (
        ast.get_source_segment(
            source,
            node,
        )
        or ""
    )

    if not segment:
        raise ValueError(f"cannot extract {function_name}")

    return {
        "name": function_name,
        "line_start": int(node.lineno),
        "line_end": int(node.end_lineno or node.lineno),
        "source": segment,
        "sha256": _sha256_text(segment),
        "node": node,
    }


def _validate_scalar_adapter(
    module_path: Path,
) -> JsonDict:

    adapter = _extract_function(
        module_path,
        "_adapter_shipping_discount",
    )

    mutant = _extract_function(
        module_path,
        "_mutant_shipping_discount",
    )

    adapter_node = adapter["node"]

    mutant_node = mutant["node"]

    if not isinstance(
        adapter_node,
        ast.FunctionDef,
    ):
        raise ValueError("invalid adapter node")

    if not isinstance(
        mutant_node,
        ast.FunctionDef,
    ):
        raise ValueError("invalid mutant node")

    if adapter_node.args.args or adapter_node.args.posonlyargs or adapter_node.args.kwonlyargs:
        raise ValueError("shipping adapter unexpectedly accepts parameters")

    def returned_literal(
        node: ast.FunctionDef,
    ) -> str:

        if len(node.body) != 1:
            raise ValueError("adapter must have exactly one statement")

        statement = node.body[0]

        if not isinstance(
            statement,
            ast.Return,
        ):
            raise ValueError("adapter is not a return")

        call = statement.value

        if not isinstance(
            call,
            ast.Call,
        ):
            raise ValueError("adapter does not return a call")

        if not (
            isinstance(
                call.func,
                ast.Name,
            )
            and call.func.id == "Decimal"
        ):
            raise ValueError("adapter does not return Decimal")

        if len(call.args) != 1 or call.keywords:
            raise ValueError("unexpected Decimal invocation")

        argument = call.args[0]

        if not (
            isinstance(
                argument,
                ast.Constant,
            )
            and isinstance(
                argument.value,
                str,
            )
        ):
            raise ValueError("Decimal argument is not a string literal")

        return argument.value

    adapter_literal = returned_literal(adapter_node)

    mutant_literal = returned_literal(mutant_node)

    if adapter_literal != "0.00":
        raise ValueError("unexpected adapter literal")

    if mutant_literal != "0.01":
        raise ValueError("unexpected mutant literal")

    return {
        "mechanism": "EXPLICIT_SCALAR_SEMANTIC_ADAPTER",
        "module": str(module_path).replace(
            "\\",
            "/",
        ),
        "module_sha256": _sha256_file(module_path),
        "adapter_function": adapter["name"],
        "adapter_function_sha256": adapter["sha256"],
        "adapter_lines": {
            "start": adapter["line_start"],
            "end": adapter["line_end"],
        },
        "adapter_literal": adapter_literal,
        "mutant_function": mutant["name"],
        "mutant_function_sha256": mutant["sha256"],
        "mutant_literal": mutant_literal,
    }


def _verify_phase_p_digest(
    proof: JsonDict,
) -> bool:

    expected = str(proof["proof_digest_sha256"])

    payload = dict(proof)

    del payload["proof_digest_sha256"]

    actual = _canonical_digest(payload)

    return actual == expected


def _validate_proof(
    *,
    proof: JsonDict,
    proof_path: Path,
    external_root: Path,
    decimal_contract_path: Path,
    adapter_module_path: Path,
) -> JsonDict:

    checks: dict[
        str,
        bool,
    ] = {}

    checks["candidate-id"] = proof.get("candidate_id") == TARGET_CANDIDATE

    checks["phase-p-status"] = proof.get("candidate_proof_status") == "PROVED_SOURCE_SLICE"

    checks["phase-p-evidence-complete"] = proof.get("evidence_complete") is True

    checks["phase-p-proof-digest"] = _verify_phase_p_digest(proof)

    checks["locked-oscar-commit"] = proof.get("locked_commit") == EXPECTED_OSCAR_COMMIT

    frozen = proof.get("frozen_candidate_metadata")

    if not isinstance(
        frozen,
        dict,
    ):
        raise ValueError("frozen candidate metadata missing")

    checks["frozen-function-sha"] = frozen.get("function_sha256") == proof.get(
        "source_slice_sha256"
    )

    checks["frozen-source-file-sha"] = frozen.get("source_file_sha256") == proof.get(
        "source_file_sha256"
    )

    source_path = external_root / str(proof["source"]) / str(proof["source_file"])

    checks["source-file-exists"] = source_path.is_file()

    actual_source_sha = _sha256_file(source_path) if source_path.is_file() else "MISSING"

    checks["source-file-sha"] = actual_source_sha == proof.get("source_file_sha256")

    source_slice = str(proof["source_slice"])

    checks["source-slice-sha"] = _sha256_text(source_slice) == proof.get("source_slice_sha256")

    obligations = proof.get("proof_obligations")

    if not isinstance(
        obligations,
        dict,
    ):
        raise ValueError("proof obligations missing")

    checks["proof-obligations"] = bool(obligations) and all(
        value is True for value in obligations.values()
    )

    runtime = proof.get("source_executed_preservation")

    if not isinstance(
        runtime,
        dict,
    ):
        raise ValueError("runtime preservation missing")

    checks["runtime-comparisons"] = runtime.get("comparisons") == 18

    checks["runtime-correct-mismatches"] = runtime.get("adapter_mismatches") == 0

    checks["runtime-mutant-sensitivity"] = runtime.get("mutant_mismatches") == 18

    symbolic = proof.get("symbolic_equivalence")

    if not isinstance(
        symbolic,
        dict,
    ):
        raise ValueError("symbolic evidence missing")

    checks["symbolic-equivalence"] = (
        symbolic.get("correct_equivalence_proved") is True
        and symbolic.get("correct_solver_status") == "unsat"
    )

    checks["symbolic-mutant"] = (
        symbolic.get("mutant_disproved") is True and symbolic.get("mutant_solver_status") == "sat"
    )

    decimal_contract = _load_json(decimal_contract_path)

    checks["decimal-contract-id"] = decimal_contract.get("contract_id") == "SC-D-DECIMAL-001"

    checks["decimal-contract-validated"] = (
        decimal_contract.get("semantic_contract_status") == "VALIDATED"
    )

    checks["required-contract"] = proof.get("required_primitive_contracts") == [
        "SC-D-DECIMAL-001",
    ]

    adapter = _validate_scalar_adapter(adapter_module_path)

    checks["explicit-scalar-adapter"] = (
        adapter["mechanism"] == "EXPLICIT_SCALAR_SEMANTIC_ADAPTER"
        and adapter["adapter_literal"] == "0.00"
        and adapter["mutant_literal"] == "0.01"
    )

    failed = [
        name
        for (
            name,
            passed,
        ) in checks.items()
        if not passed
    ]

    return {
        "checks": checks,
        "failed_checks": failed,
        "source_path": str(source_path).replace(
            "\\",
            "/",
        ),
        "actual_source_sha256": actual_source_sha,
        "proof_file_sha256": _sha256_file(proof_path),
        "decimal_contract_sha256": _sha256_file(decimal_contract_path),
        "adapter": adapter,
        "passed": not failed,
    }


def build_terminal_certificate(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    phase_p_root = repo_root / ("benchmarks/v0.11/candidate_proof_frontier")

    proof_path = phase_p_root / "shipping_discount_proof.json"

    frontier_path = phase_p_root / "candidate_frontier.jsonl"

    proof = _load_json(proof_path)

    frontier = _load_jsonl(frontier_path)

    if len(frontier) != 90:
        raise ValueError("frontier must contain 90 candidates")

    terminal_policy_path = repo_root / (
        "benchmarks/v0.11/terminal_policy/semantic_ambiguity_policy.json"
    )

    terminal_policy = _load_json(terminal_policy_path)

    if terminal_policy.get("frozen_before_terminal_outcome_assignment") is not True:
        raise ValueError("terminal policy was not frozen")

    configured_outcomes = set(
        terminal_policy.get(
            "terminal_outcomes",
            [],
        )
    )

    if configured_outcomes != TERMINAL_OUTCOMES:
        raise ValueError("terminal outcome set changed")

    protocol_path = repo_root / "experiments/V0.11_PROTOCOL.md"

    protocol_levels = _protocol_levels(protocol_path)

    decimal_contract_path = repo_root / (
        "benchmarks/v0.11/semantic_contracts/decimal_contract.json"
    )

    adapter_module_path = repo_root / ("src/bizproof/generalization_candidate_proof.py")

    evidence = _validate_proof(
        proof=proof,
        proof_path=proof_path,
        external_root=repo_root / "external_sources/v0.6",
        decimal_contract_path=decimal_contract_path,
        adapter_module_path=adapter_module_path,
    )

    if evidence["passed"] is not True:
        raise ValueError(
            "terminal certificate evidence failed: " + ", ".join(evidence["failed_checks"])
        )

    explicit_adapter = True

    declarative_bindings = bool(proof.get("required_primitive_contracts"))

    terminal_outcome = _classify_certified_level(
        explicit_scalar_adapter=explicit_adapter,
        declarative_bindings=declarative_bindings,
    )

    if terminal_outcome != "CERTIFIED_A2":
        raise ValueError("unexpected terminal outcome: " + terminal_outcome)

    certificate: JsonDict = {
        "schema_version": ("BIZPROOF-V0.11-TERMINAL-CERTIFICATE-1"),
        "certificate_id": CERTIFICATE_ID,
        "status": terminal_outcome,
        "terminal_outcome": terminal_outcome,
        "candidate_id": TARGET_CANDIDATE,
        "certification_scope": "RETURN_EXPRESSION",
        "claim_scope": (
            "Certification applies only to the "
            "locked AbstractBenefit.shipping_discount "
            "source slice represented by this "
            "evidence bundle; it does not certify "
            "the complete django-oscar framework."
        ),
        "cohort": {
            "sha256": COHORT_SHA256,
            "sample_size": 90,
        },
        "provenance": {
            "source_id": proof["source"],
            "resolved_commit": proof["locked_commit"],
            "external_source": proof["source_file"],
            "external_source_sha256": proof["source_file_sha256"],
            "source_slice_sha256": proof["source_slice_sha256"],
            "source_lines": proof["source_lines"],
        },
        "assistance": {
            "level": "A2",
            "terminal_outcome": "CERTIFIED_A2",
            "protocol_definition": protocol_levels["CERTIFIED_A2"],
            "explicit_scalar_adapter": evidence["adapter"],
            "declarative_primitive_contracts": proof["required_primitive_contracts"],
            "classification_precedence": (
                "explicit scalar adapter takes precedence over declarative bindings"
            ),
        },
        "artifacts": {
            "phase_p_proof": str(proof_path.relative_to(repo_root)).replace(
                "\\",
                "/",
            ),
            "phase_p_proof_sha256": evidence["proof_file_sha256"],
            "decimal_contract": str(decimal_contract_path.relative_to(repo_root)).replace(
                "\\",
                "/",
            ),
            "decimal_contract_sha256": evidence["decimal_contract_sha256"],
            "adapter_module": str(adapter_module_path.relative_to(repo_root)).replace(
                "\\",
                "/",
            ),
            "adapter_module_sha256": evidence["adapter"]["module_sha256"],
        },
        "evidence": {
            "phase_p_proof_digest": proof["proof_digest_sha256"],
            "semantic_contracts": {
                "required": proof["required_primitive_contracts"],
                "satisfied": proof["primitive_contracts_satisfied"],
            },
            "source_executed_preservation": {
                "comparisons": proof["source_executed_preservation"]["comparisons"],
                "correct_mismatches": proof["source_executed_preservation"]["adapter_mismatches"],
                "mutant_mismatches": proof["source_executed_preservation"]["mutant_mismatches"],
            },
            "symbolic_equivalence": {
                "correct_verdict": "PROVED",
                "solver_status": proof["symbolic_equivalence"]["correct_solver_status"],
                "mutant_verdict": "DISPROVED",
                "mutant_solver_status": proof["symbolic_equivalence"]["mutant_solver_status"],
            },
        },
        "checks": evidence["checks"],
        "failed_checks": evidence["failed_checks"],
        "terminal_outcome_assigned": True,
        "final_study_complete": False,
    }

    digest_payload = dict(certificate)

    certificate["certificate_digest"] = _canonical_digest(digest_payload)

    candidate_states: list[JsonDict] = []

    for item in frontier:
        candidate_id = str(item["candidate_id"])

        if candidate_id == TARGET_CANDIDATE:
            candidate_states.append(
                {
                    "candidate_id": candidate_id,
                    "state": "TERMINAL_ASSIGNED",
                    "terminal_outcome": "CERTIFIED_A2",
                    "certificate_id": CERTIFICATE_ID,
                    "certificate_digest": certificate["certificate_digest"],
                }
            )

        else:
            candidate_states.append(
                {
                    "candidate_id": candidate_id,
                    "state": "PENDING_UNASSIGNED",
                    "terminal_outcome": None,
                    "certificate_id": None,
                }
            )

    if len(candidate_states) != 90:
        raise ValueError("terminal-state record count changed")

    assigned = [item for item in candidate_states if (item["state"] == "TERMINAL_ASSIGNED")]

    pending = [item for item in candidate_states if (item["state"] == "PENDING_UNASSIGNED")]

    if len(assigned) != 1:
        raise ValueError("expected one terminal assignment")

    if len(pending) != 89:
        raise ValueError("expected 89 pending candidates")

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "FIRST_TERMINAL_CERTIFICATION",
        "cohort_size": 90,
        "terminal_outcomes_assigned": 1,
        "terminal_outcomes_pending": 89,
        "certificates_issued": 1,
        "certificates_failed": 0,
        "terminal_distribution": {
            "CERTIFIED_A0": 0,
            "CERTIFIED_A1": 0,
            "CERTIFIED_A2": 1,
            "NOT_CERTIFIED_UNKNOWN": 0,
            "NOT_CERTIFIED_UNSUPPORTED": 0,
            "NOT_CERTIFIED_PROVENANCE": 0,
            "NOT_CERTIFIED_EXECUTION": 0,
            "NOT_CERTIFIED_SEMANTIC_AMBIGUITY": 0,
        },
        "first_certificate_id": CERTIFICATE_ID,
        "first_candidate_id": TARGET_CANDIDATE,
        "first_terminal_outcome": "CERTIFIED_A2",
        "weighted_metrics_ready": False,
        "final_certification_complete": False,
        "partial_certification_claim": True,
        "claim_scope": certificate["claim_scope"],
        "passed": True,
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    certificate_path = output_dir / f"{CERTIFICATE_ID}.json"

    certificate_path.write_text(
        json.dumps(
            certificate,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "candidate_terminal_state.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in candidate_states
        ),
        encoding="utf-8",
    )

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
                ("# BIZPROOF V0.11 First Terminal Certification"),
                "",
                "## Scope",
                "",
                str(certificate["claim_scope"]),
                "",
                "## Result",
                "",
                (f"- Candidate: `{TARGET_CANDIDATE}`"),
                (f"- Certificate: `{CERTIFICATE_ID}`"),
                ("- Terminal outcome: `CERTIFIED_A2`"),
                ("- Source-executed comparisons: 18"),
                ("- Correct-adapter mismatches: 0"),
                ("- Mutant mismatches: 18"),
                ("- Symbolic equivalence: PROVED (`unsat`)"),
                ("- Symbolic mutant: DISPROVED (`sat`)"),
                ("- Candidates terminalized: 1 / 90"),
                ("- Candidates pending: 89 / 90"),
                "",
                (
                    "No overall V0.11 certification "
                    "yield is reported until all 90 "
                    "sampled candidates receive a "
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
        default=Path("benchmarks/v0.11/terminal_certification"),
    )

    args = parser.parse_args()

    summary = build_terminal_certificate(
        repo_root=args.repo_root.resolve(),
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 first terminal certification")

    print(
        "Candidate:",
        summary["first_candidate_id"],
    )

    print(
        "Certificate:",
        summary["first_certificate_id"],
    )

    print(
        "Terminal outcome:",
        summary["first_terminal_outcome"],
    )

    print(
        "Certificates issued:",
        summary["certificates_issued"],
    )

    print(
        "Terminalized:",
        summary["terminal_outcomes_assigned"],
        "/ 90",
    )

    print(
        "Pending:",
        summary["terminal_outcomes_pending"],
        "/ 90",
    )

    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
