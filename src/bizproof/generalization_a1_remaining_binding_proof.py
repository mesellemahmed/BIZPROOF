from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import z3

from .generalization_a1_batch_proof import (
    ALLOWED_SEMANTIC_ABSTRACTIONS,
    ProofUnsupported,
    SourceCompiler,
    _canonical_digest,
    _canonical_expression,
    _compile_ir,
    _model_witness,
    _mutate_ir,
    _protocol_a1,
    _replay_equivalence,
    _validated_semantic_contracts,
)

JsonDict = dict[str, Any]


TARGETS = {
    "019d3a3df4514bac",
    "051c7ef379178030",
    "1458ed128652b359",
    "4c7af63af2f89319",
    "635fe113a02cf90b",
    "972b76d53a12b8ad",
    "a74d4580a9effb73",
    "cb937575ad9957d1",
    "dfd34c86bcd9bfa1",
    "eb41eb351df073ef",
    "eff10167a5398559",
    "fd4702ed1d79ff1f",
}


EXPECTED_SOURCE_COMMITS = {
    "openfisca_france": "ebcb7782d17058495c6ca33c278e373e167b641b",
    "django_oscar": "5699d78449954f047d6d715fd2b6c5d19594e0f3",
}


# These calls represent declarative external observations.
# Their result can be bound without giving BIZPROOF its
# own handwritten business semantics.
SAFE_DECLARATIVE_CALLS = {
    "individu",
    "foyer_fiscal",
    "famille",
    "has_role",
    "menage",
    "period",
    "parameters",
}


class BindingAwareSourceCompiler(SourceCompiler):
    def expression(
        self,
        node: ast.expr,
    ) -> Any:

        # Phase-S already performs this lookup for ast.Call.
        # W4 generalizes exactly the same rule to every
        # explicitly declared source expression.
        try:
            expression = _canonical_expression(ast.unparse(node))

        except Exception:
            expression = None

        if expression is not None and expression in self.binding_variables:
            self.used_bindings.add(expression)

            return self.binding_variables[expression]

        return super().expression(node)


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
            raise ValueError("expected JSON object: " + str(path))

        result.append(value)

    return result


def _sha256_file(
    path: Path,
) -> str:

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(
    value: str,
) -> str:

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _extract_function(
    source: str,
    *,
    function_name: str,
    line_start: int,
    line_end: int,
) -> tuple[
    ast.FunctionDef,
    str,
]:

    tree = ast.parse(source)

    functions = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name == function_name
            and node.lineno >= line_start
            and node.lineno <= line_end
        )
    ]

    if len(functions) != 1:
        raise ProofUnsupported("expected exactly one source function, got " + str(len(functions)))

    node = functions[0]

    segment = ast.get_source_segment(
        source,
        node,
    )

    if segment is None:
        raise ProofUnsupported("unable to recover source function")

    return (
        node,
        segment,
    )


def _validate_binding_semantics(
    required: list[JsonDict],
    validated_contracts: dict[
        str,
        str,
    ],
) -> dict[str, str]:

    used_contracts: dict[
        str,
        str,
    ] = {}

    for binding in required:
        kind = str(
            binding.get(
                "kind",
                "",
            )
        )

        primitive = str(
            binding.get(
                "primitive",
                "",
            )
        )

        if kind != "CALL":
            continue

        if primitive in (ALLOWED_SEMANTIC_ABSTRACTIONS):
            expected = ALLOWED_SEMANTIC_ABSTRACTIONS[primitive]

            actual = validated_contracts.get(primitive)

            if actual != expected:
                raise ProofUnsupported("semantic contract unavailable for primitive " + primitive)

            used_contracts[primitive] = actual

            continue

        if primitive in (SAFE_DECLARATIVE_CALLS):
            continue

        raise ProofUnsupported(
            "unvalidated helper/domain call cannot be abstracted as A1 binding: " + primitive
        )

    return used_contracts


def _mutant_witness_replay(
    *,
    source_expression: Any,
    mutant_expression: Any,
    variables: dict[
        str,
        Any,
    ],
    witness: dict[
        str,
        str,
    ],
) -> bool:

    substitutions = []

    for name, variable in variables.items():
        value = witness.get(
            name,
            "0",
        )

        substitutions.append(
            (
                variable,
                z3.RealVal(value),
            )
        )

    source_value = z3.simplify(
        z3.substitute(
            source_expression,
            *substitutions,
        )
    )

    mutant_value = z3.simplify(
        z3.substitute(
            mutant_expression,
            *substitutions,
        )
    )

    return bool(z3.is_true(z3.simplify(source_value != mutant_value)))


def _prove_candidate(
    *,
    repo_root: Path,
    probe: JsonDict,
    validated_contracts: dict[
        str,
        str,
    ],
) -> JsonDict:

    candidate_id = str(probe["candidate_id"])

    result: JsonDict = {
        "candidate_id": candidate_id,
        "source": probe.get("source_id"),
        "class": probe.get("enclosing_class"),
        "function": probe.get("function"),
        "status": "PROOF_REVIEW_REQUIRED",
        "terminal_outcome": None,
        "certification_claim": False,
    }

    try:
        source_id = str(probe["source_id"])

        expected_commit = EXPECTED_SOURCE_COMMITS.get(source_id)

        if expected_commit is None:
            raise ProofUnsupported("source commit policy absent: " + source_id)

        resolved_commit = str(probe["resolved_commit"])

        if resolved_commit != expected_commit:
            raise ProofUnsupported("locked source commit mismatch")

        file_name = str(probe["file"])

        source_path = repo_root / "external_sources/v0.6" / source_id / file_name

        if not source_path.is_file():
            raise ProofUnsupported("locked source file missing")

        source_file_sha256 = _sha256_file(source_path)

        source_text = source_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        _, source_slice = _extract_function(
            source_text,
            function_name=str(probe["function"]),
            line_start=int(probe["line_start"]),
            line_end=int(probe["line_end"]),
        )

        function_sha256 = _sha256_text(source_slice)

        required_raw = probe.get(
            "required_bindings",
            [],
        )

        if not isinstance(
            required_raw,
            list,
        ):
            raise ProofUnsupported("invalid required bindings")

        required: list[JsonDict] = []

        for raw_binding in required_raw:
            if not isinstance(
                raw_binding,
                dict,
            ):
                raise ProofUnsupported("invalid binding record")

            required.append(raw_binding)

        if not required:
            raise ProofUnsupported("candidate has no declared bindings")

        binding_ids = [str(binding["binding_id"]) for binding in required]

        if len(binding_ids) != len(set(binding_ids)):
            raise ProofUnsupported("duplicate binding IDs")

        binding_expressions = [
            _canonical_expression(str(binding["source_expression"])) for binding in required
        ]

        if len(binding_expressions) != len(set(binding_expressions)):
            raise ProofUnsupported("duplicate source binding expressions")

        semantic_contracts = _validate_binding_semantics(
            required,
            validated_contracts,
        )

        raw_ir = probe.get("ir")

        if not isinstance(
            raw_ir,
            dict,
        ):
            raise ProofUnsupported("frozen BSIR missing")

        return_ir = raw_ir.get("return")

        if return_ir is None:
            raise ProofUnsupported("frozen BSIR return missing")

        expected_ir_sha = probe.get("ir_sha256")

        if expected_ir_sha:
            actual_ir_sha = _canonical_digest(raw_ir)

            if str(expected_ir_sha) != actual_ir_sha:
                raise ProofUnsupported("frozen BSIR digest mismatch")

        variable_by_expression: dict[
            str,
            Any,
        ] = {}

        variable_by_binding_id: dict[
            str,
            Any,
        ] = {}

        variables: dict[
            str,
            Any,
        ] = {}

        for index, binding in enumerate(required):
            binding_id = str(binding["binding_id"])

            source_expression = _canonical_expression(str(binding["source_expression"]))

            variable_name = "b_" + candidate_id[:6] + "_" + str(index)

            variable = z3.Real(variable_name)

            variables[variable_name] = variable

            variable_by_expression[source_expression] = variable

            variable_by_binding_id[binding_id] = variable

        compiler = BindingAwareSourceCompiler(variable_by_expression)

        source_expression = compiler.function(source_slice)

        bsir_expression = _compile_ir(
            return_ir,
            variable_by_binding_id,
        )

        correct_solver = z3.Solver()

        correct_solver.add(source_expression != bsir_expression)

        correct_status = correct_solver.check()

        if correct_status != z3.unsat:
            raise ProofUnsupported("source/BSIR disequality is not UNSAT: " + str(correct_status))

        replay_count = _replay_equivalence(
            source_expression,
            bsir_expression,
            variables,
        )

        mutant_ir, mutation = _mutate_ir(return_ir)

        mutant_expression = _compile_ir(
            mutant_ir,
            variable_by_binding_id,
        )

        mutant_solver = z3.Solver()

        mutant_solver.add(source_expression != mutant_expression)

        mutant_status = mutant_solver.check()

        if mutant_status != z3.sat:
            raise ProofUnsupported(
                "structural mutant did not produce SAT witness: " + str(mutant_status)
            )

        witness = _model_witness(
            mutant_solver.model(),
            variables,
        )

        if not (
            _mutant_witness_replay(
                source_expression=source_expression,
                mutant_expression=mutant_expression,
                variables=variables,
                witness=witness,
            )
        ):
            raise ProofUnsupported("mutant witness replay failed")

        expected_expressions = set(binding_expressions)

        used_expressions = set(compiler.used_bindings)

        undeclared_used = used_expressions - expected_expressions

        if undeclared_used:
            raise ProofUnsupported("source compiler used undeclared bindings")

        result.update(
            {
                "status": "PROVED_A1_SOURCE_TO_BSIR",
                "terminal_outcome": "CERTIFIED_A1",
                "certification_claim": True,
                "source_file": file_name,
                "source_file_sha256": source_file_sha256,
                "resolved_commit": resolved_commit,
                "function_sha256": function_sha256,
                "probe_status_before_w4": probe.get("probe_status"),
                "binding_count": len(required),
                "bindings": required,
                "used_source_bindings": sorted(used_expressions),
                "unused_declared_bindings": sorted(expected_expressions - used_expressions),
                "semantic_contracts": semantic_contracts,
                "ir_sha256": probe.get("ir_sha256"),
                "correct_solver_status": str(correct_status),
                "mutant_solver_status": str(mutant_status),
                "concrete_replays": replay_count,
                "mutation": mutation,
                "mutant_witness": witness,
                "proof_obligations": {
                    "locked_source_commit": True,
                    "frozen_bsir": True,
                    "declarative_bindings": True,
                    "validated_semantic_abstractions": True,
                    "independent_source_ast_compile": True,
                    "bsir_compile": True,
                    "symbolic_equivalence_unsat": True,
                    "concrete_replay": True,
                    "mutant_detected_sat": True,
                    "mutant_witness_replayed": True,
                },
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


def build(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    probes = _load_jsonl(repo_root / ("benchmarks/v0.11/symbolic_probe/probe.jsonl"))

    probe_by_id = {
        str(item["candidate_id"]): item
        for item in probes
        if (str(item.get("candidate_id")) in TARGETS)
    }

    if set(probe_by_id) != TARGETS:
        missing = sorted(TARGETS - set(probe_by_id))

        raise ValueError("W4 probe coverage mismatch; missing=" + repr(missing))

    prior_states = _load_jsonl(
        repo_root / ("benchmarks/v0.11/a1_leaf_binding_batch/candidate_terminal_state.jsonl")
    )

    if len(prior_states) != 90:
        raise ValueError("W2 ledger must contain 90 candidates")

    prior_by_id = {str(item["candidate_id"]): item for item in prior_states}

    for candidate_id in TARGETS:
        if prior_by_id[candidate_id]["state"] != "PENDING_UNASSIGNED":
            raise ValueError("W4 candidate no longer pending: " + candidate_id)

    validated_contracts = _validated_semantic_contracts(repo_root)

    proofs = [
        _prove_candidate(
            repo_root=repo_root,
            probe=probe_by_id[candidate_id],
            validated_contracts=validated_contracts,
        )
        for candidate_id in sorted(TARGETS)
    ]

    proved = [item for item in proofs if (item["status"] == "PROVED_A1_SOURCE_TO_BSIR")]

    reviews = [item for item in proofs if (item["status"] != "PROVED_A1_SOURCE_TO_BSIR")]

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    certificate_dir = output_dir / "certificates"

    certificate_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in certificate_dir.glob("*.json"):
        path.unlink()

    protocol = _protocol_a1(repo_root / "experiments/V0.11_PROTOCOL.md")

    certificates: list[JsonDict] = []

    for proof in proved:
        candidate_id = str(proof["candidate_id"])

        certificate: JsonDict = {
            "schema_version": ("BIZPROOF-V0.11-A1-CERTIFICATE-1"),
            "certificate_id": ("CERT-V011-A1-" + candidate_id.upper()),
            "candidate_id": candidate_id,
            "status": "CERTIFIED_A1",
            "terminal_outcome": "CERTIFIED_A1",
            "assistance_level": "A1",
            "protocol_definition": protocol,
            "authoring_mode": ("DECLARATIVE_BINDINGS_FROZEN_BSIR"),
            "source": {
                "source_id": proof["source"],
                "class": proof["class"],
                "function": proof["function"],
                "file": proof["source_file"],
                "resolved_commit": proof["resolved_commit"],
                "source_file_sha256": proof["source_file_sha256"],
                "function_sha256": proof["function_sha256"],
            },
            "bindings": proof["bindings"],
            "semantic_contracts": proof["semantic_contracts"],
            "evidence": {
                "proof_digest": proof["proof_digest"],
                "ir_sha256": proof["ir_sha256"],
                "correct_solver_status": proof["correct_solver_status"],
                "mutant_solver_status": proof["mutant_solver_status"],
                "concrete_replays": proof["concrete_replays"],
                "mutation": proof["mutation"],
                "mutant_witness": proof["mutant_witness"],
                "proof_obligations": proof["proof_obligations"],
            },
            "claim_scope": (
                "Certification proves equivalence "
                "between the locked source AST and "
                "the frozen BSIR under the explicit "
                "declarative bindings listed here. "
                "External framework/database values "
                "and helper semantics without a "
                "validated semantic contract remain "
                "outside the certificate."
            ),
            "terminal_outcome_assigned": True,
            "final_study_complete": False,
        }

        certificate["certificate_digest"] = _canonical_digest(dict(certificate))

        certificates.append(certificate)

        (certificate_dir / (certificate["certificate_id"] + ".json")).write_text(
            json.dumps(
                certificate,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
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

    (output_dir / "review.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in reviews
        ),
        encoding="utf-8",
    )

    certificate_by_id = {str(item["candidate_id"]): item for item in certificates}

    states: list[JsonDict] = []

    for previous in prior_states:
        candidate_id = str(previous["candidate_id"])

        matched_certificate = certificate_by_id.get(candidate_id)

        if matched_certificate is None:
            states.append(dict(previous))

            continue

        if previous["state"] != "PENDING_UNASSIGNED":
            raise ValueError("refusing terminal overwrite: " + candidate_id)

        states.append(
            {
                "candidate_id": candidate_id,
                "state": "TERMINAL_ASSIGNED",
                "terminal_outcome": "CERTIFIED_A1",
                "certificate_id": matched_certificate["certificate_id"],
                "certificate_digest": matched_certificate["certificate_digest"],
            }
        )

    assigned = [item for item in states if (item["state"] == "TERMINAL_ASSIGNED")]

    pending = [item for item in states if (item["state"] == "PENDING_UNASSIGNED")]

    (output_dir / "candidate_terminal_state.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in states
        ),
        encoding="utf-8",
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "A1_REMAINING_DECLARATIVE_BINDINGS",
        "candidates_attempted": 12,
        "candidates_proved": len(proved),
        "certificates_issued": len(certificates),
        "review_required": len(reviews),
        "proved_candidate_ids": sorted(str(item["candidate_id"]) for item in proved),
        "review_candidate_ids": sorted(str(item["candidate_id"]) for item in reviews),
        "terminalized_before": 57,
        "terminalized_after": len(assigned),
        "pending_after": len(pending),
        "final_certification_complete": False,
        "weighted_metrics_ready": False,
        "passed": (len(proofs) == 12 and (len(proved) + len(reviews) == 12) and len(states) == 90),
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
                ("# BIZPROOF V0.11 Remaining Declarative A1 Binding Proofs"),
                "",
                ("- Candidates attempted: 12"),
                (f"- CERTIFIED_A1: {len(certificates)}"),
                (f"- Review required: {len(reviews)}"),
                "",
                ("This phase reuses the Phase-S proof kernel."),
                "",
                (
                    "Source expressions explicitly "
                    "declared as bindings may be "
                    "abstracted regardless of whether "
                    "their AST root is Call, Attribute "
                    "or Name."
                ),
                "",
                (
                    "Helper/domain calls that are not "
                    "simple external observations "
                    "require a validated semantic "
                    "contract. They remain pending "
                    "otherwise."
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
        default=Path("benchmarks/v0.11/a1_remaining_binding_proofs"),
    )

    args = parser.parse_args()

    repo_root = args.repo_root.resolve()

    output_dir = args.output_dir

    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    summary = build(
        repo_root=repo_root,
        output_dir=output_dir.resolve(),
    )

    print("BIZPROOF V0.11 W4")

    print(
        "Attempted:",
        summary["candidates_attempted"],
    )

    print(
        "CERTIFIED_A1:",
        summary["certificates_issued"],
    )

    print(
        "Review required:",
        summary["review_required"],
    )

    print(
        "Terminalized:",
        summary["terminalized_after"],
        "/90",
    )

    print(
        "Pending:",
        summary["pending_after"],
        "/90",
    )

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
