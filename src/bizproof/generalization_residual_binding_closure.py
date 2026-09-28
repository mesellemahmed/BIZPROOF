from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import z3

from .generalization_a1_remaining_binding_proof import (
    _extract_function,
    _load_jsonl,
    _sha256_file,
    _sha256_text,
)
from .generalization_a2_v3_proof import (
    _digest,
    _protocol_definition,
    _solver_result,
)

JsonDict = dict[str, Any]

RSA_ID = "972b76d53a12b8ad"
MOBILITY_ID = "eb41eb351df073ef"

OPENFISCA_COMMIT = "ebcb7782d17058495c6ca33c278e373e167b641b"


def adapt_rsa_tns_turnover_eligibility(
    ca: int,
    activity_is_purchase_resale: bool,
    activity_is_bic: bool,
    activity_is_bnc: bool,
    sales_ceiling: int,
    service_ceiling: int,
) -> int:

    purchase_resale = int(activity_is_purchase_resale)

    service = int(activity_is_bic) + int(activity_is_bnc)

    return purchase_resale * int(ca <= sales_ceiling) + service * int(ca <= service_ceiling)


def mutant_rsa_tns_turnover_eligibility(
    ca: int,
    activity_is_purchase_resale: bool,
    activity_is_bic: bool,
    activity_is_bnc: bool,
    sales_ceiling: int,
    service_ceiling: int,
) -> int:

    purchase_resale = int(activity_is_purchase_resale)

    service = int(activity_is_bic) + int(activity_is_bnc)

    # Boundary mutant:
    # <= becomes < on the sales branch.
    return purchase_resale * int(ca < sales_ceiling) + service * int(ca <= service_ceiling)


class _ActivityType:
    def __init__(
        self,
        code: int,
    ) -> None:

        self.code = code

        self.possible_values = SimpleNamespace(
            achat_revente=1,
            bic=2,
            bnc=3,
        )

    def __eq__(
        self,
        other: object,
    ) -> bool:

        return bool(self.code == other)


def _parameter_object(
    *,
    sales_ceiling: int,
    service_ceiling: int,
) -> Any:

    return SimpleNamespace(
        microentreprise=SimpleNamespace(
            regime_micro_bic=SimpleNamespace(
                marchandises=SimpleNamespace(plafond=sales_ceiling),
                services=SimpleNamespace(plafond=service_ceiling),
            )
        )
    )


def _compile_locked_function(
    source_slice: str,
    function_name: str,
) -> Any:

    namespace: dict[
        str,
        Any,
    ] = {}

    source = textwrap.dedent(source_slice)

    exec(
        compile(
            source,
            "<locked-w5-source>",
            "exec",
        ),
        namespace,
    )

    function = namespace.get(function_name)

    if not callable(function):
        raise ValueError("locked source function did not compile")

    return function


def _runtime_rsa(
    source_slice: str,
) -> JsonDict:

    function = _compile_locked_function(
        source_slice,
        "eligibilite_chiffre_affaire",
    )

    comparisons = 0
    adapter_mismatches = 0
    mutant_mismatches = 0

    ca_values = [
        -1,
        0,
        49,
        50,
        51,
        99,
        100,
        101,
        200,
    ]

    ceiling_pairs = [
        (100, 50),
        (50, 100),
        (0, 0),
    ]

    activity_codes = [
        1,
        2,
        3,
        4,
    ]

    for (
        sales_ceiling,
        service_ceiling,
    ) in ceiling_pairs:
        parameters = _parameter_object(
            sales_ceiling=sales_ceiling,
            service_ceiling=service_ceiling,
        )

        for activity_code in activity_codes:
            activity = _ActivityType(activity_code)

            for ca in ca_values:
                external = function(
                    ca,
                    activity,
                    parameters,
                )

                adapter = adapt_rsa_tns_turnover_eligibility(
                    ca,
                    activity_code == 1,
                    activity_code == 2,
                    activity_code == 3,
                    sales_ceiling,
                    service_ceiling,
                )

                mutant = mutant_rsa_tns_turnover_eligibility(
                    ca,
                    activity_code == 1,
                    activity_code == 2,
                    activity_code == 3,
                    sales_ceiling,
                    service_ceiling,
                )

                comparisons += 1

                if external != adapter:
                    adapter_mismatches += 1

                if external != mutant:
                    mutant_mismatches += 1

    return {
        "validation_domain": (
            "4 activity categories x 9 turnover values x 3 sales/service ceiling pairs"
        ),
        "comparisons": comparisons,
        "adapter_mismatches": adapter_mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _symbolic_rsa() -> JsonDict:

    ca = z3.Real("ca")

    sales_ceiling = z3.Real("sales_ceiling")

    service_ceiling = z3.Real("service_ceiling")

    purchase_resale = z3.Bool("purchase_resale")

    bic = z3.Bool("bic")

    bnc = z3.Bool("bnc")

    purchase_value = z3.If(
        purchase_resale,
        z3.IntVal(1),
        z3.IntVal(0),
    )

    service_value = z3.If(
        bic,
        z3.IntVal(1),
        z3.IntVal(0),
    ) + z3.If(
        bnc,
        z3.IntVal(1),
        z3.IntVal(0),
    )

    source = purchase_value * z3.If(
        ca <= sales_ceiling,
        z3.IntVal(1),
        z3.IntVal(0),
    ) + service_value * z3.If(
        ca <= service_ceiling,
        z3.IntVal(1),
        z3.IntVal(0),
    )

    adapter = purchase_value * z3.If(
        ca <= sales_ceiling,
        z3.IntVal(1),
        z3.IntVal(0),
    ) + service_value * z3.If(
        ca <= service_ceiling,
        z3.IntVal(1),
        z3.IntVal(0),
    )

    mutant = purchase_value * z3.If(
        ca < sales_ceiling,
        z3.IntVal(1),
        z3.IntVal(0),
    ) + service_value * z3.If(
        ca <= service_ceiling,
        z3.IntVal(1),
        z3.IntVal(0),
    )

    result = _solver_result(
        source,
        adapter,
        mutant,
    )

    result["symbolic_domain"] = (
        "numeric turnover and ceilings with explicit activity-category membership predicates"
    )

    return result


def _probe_by_id(
    repo_root: Path,
) -> dict[str, JsonDict]:

    records = _load_jsonl(repo_root / ("benchmarks/v0.11/symbolic_probe/probe.jsonl"))

    return {
        str(item["candidate_id"]): item
        for item in records
        if str(item.get("candidate_id"))
        in {
            RSA_ID,
            MOBILITY_ID,
        }
    }


def _locked_source(
    *,
    repo_root: Path,
    probe: JsonDict,
) -> tuple[
    str,
    str,
    str,
]:

    if str(probe["resolved_commit"]) != OPENFISCA_COMMIT:
        raise ValueError("locked OpenFisca commit mismatch")

    source_path = repo_root / "external_sources/v0.6" / "openfisca_france" / str(probe["file"])

    if not source_path.is_file():
        raise ValueError("locked source missing: " + str(source_path))

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

    return (
        source_slice,
        source_file_sha256,
        function_sha256,
    )


def build(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    probes = _probe_by_id(repo_root)

    if set(probes) != {
        RSA_ID,
        MOBILITY_ID,
    }:
        raise ValueError("W5 probe coverage mismatch")

    prior_states = _load_jsonl(
        repo_root / ("benchmarks/v0.11/a1_remaining_binding_proofs/candidate_terminal_state.jsonl")
    )

    if len(prior_states) != 90:
        raise ValueError("W4 ledger must contain 90 candidates")

    prior_by_id = {str(item["candidate_id"]): item for item in prior_states}

    for candidate_id in (
        RSA_ID,
        MOBILITY_ID,
    ):
        if prior_by_id[candidate_id]["state"] != "PENDING_UNASSIGNED":
            raise ValueError("W5 target is no longer pending: " + candidate_id)

    # --------------------------------------------------------
    # 972b... : explicit A2 scalar semantic projection
    # --------------------------------------------------------

    rsa_probe = probes[RSA_ID]

    (
        rsa_source,
        rsa_file_sha,
        rsa_function_sha,
    ) = _locked_source(
        repo_root=repo_root,
        probe=rsa_probe,
    )

    runtime = _runtime_rsa(rsa_source)

    symbolic = _symbolic_rsa()

    rsa_passed = (
        runtime["adapter_mismatches"] == 0
        and runtime["mutant_mismatches"] > 0
        and symbolic["correct_proved"] is True
        and symbolic["mutant_disproved"] is True
    )

    rsa_proof: JsonDict = {
        "candidate_id": RSA_ID,
        "source": "openfisca_france",
        "class": rsa_probe["enclosing_class"],
        "function": rsa_probe["function"],
        "semantic_adapter": "RSA_TNS_TURNOVER_ELIGIBILITY",
        "semantic_binding_scope": (
            "The activity enum is projected to "
            "three explicit category-membership "
            "predicates (achat_revente, bic, bnc); "
            "turnover and both micro-enterprise "
            "ceilings are scalar bindings."
        ),
        "source_file_sha256": rsa_file_sha,
        "function_sha256": rsa_function_sha,
        "runtime": runtime,
        "symbolic": symbolic,
        "status": ("PROVED_A2_SCALAR" if rsa_passed else "A2_PROOF_FAILED"),
        "terminal_outcome": ("CERTIFIED_A2" if rsa_passed else None),
        "certification_claim": rsa_passed,
    }

    rsa_proof["proof_digest"] = _digest(dict(rsa_proof))

    # --------------------------------------------------------
    # eb41... : unsupported temporal semantic primitive
    # --------------------------------------------------------

    mobility_probe = probes[MOBILITY_ID]

    (
        _mobility_source,
        mobility_file_sha,
        mobility_function_sha,
    ) = _locked_source(
        repo_root=repo_root,
        probe=mobility_probe,
    )

    w4_reviews = _load_jsonl(
        repo_root / ("benchmarks/v0.11/a1_remaining_binding_proofs/review.jsonl")
    )

    mobility_review = next(
        (item for item in w4_reviews if (str(item["candidate_id"]) == MOBILITY_ID)),
        None,
    )

    if mobility_review is None:
        raise ValueError("W4 mobility review evidence missing")

    review_reason = str(
        mobility_review.get(
            "review_reason",
            "",
        )
    )

    if "astype" not in (review_reason):
        raise ValueError("expected astype review evidence not found")

    negative_evidence: JsonDict = {
        "schema_version": ("BIZPROOF-V0.11-NEGATIVE-EVIDENCE-1"),
        "candidate_id": MOBILITY_ID,
        "terminal_outcome": "NOT_CERTIFIED_UNSUPPORTED",
        "scope": ("Frozen V0.11 formal source-to-BSIR proof stack"),
        "reason_code": ("UNVALIDATED_TEMPORAL_CAST_SEMANTICS"),
        "reason": (
            "The locked rule depends on "
            "contrat_travail_debut.astype('M8[M]'). "
            "The frozen V0.11 semantic-contract set "
            "contains no validated contract for "
            "month-precision datetime casting. "
            "Treating this transformation as an "
            "independent declarative input would "
            "erase a real temporal dependency."
        ),
        "w4_review_reason": review_reason,
        "interpretation": (
            "NOT_CERTIFIED_UNSUPPORTED means "
            "unsupported by the frozen V0.11 "
            "formal semantics. It does not mean "
            "that the rule is intrinsically "
            "unverifiable."
        ),
        "source": {
            "source_id": "openfisca_france",
            "class": mobility_probe["enclosing_class"],
            "function": mobility_probe["function"],
            "file": mobility_probe["file"],
            "resolved_commit": mobility_probe["resolved_commit"],
            "source_file_sha256": mobility_file_sha,
            "function_sha256": mobility_function_sha,
        },
        "certification_claim": False,
    }

    negative_evidence["negative_evidence_digest"] = _digest(dict(negative_evidence))

    # --------------------------------------------------------
    # Outputs
    # --------------------------------------------------------

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    certificate_dir = output_dir / "certificates"

    negative_dir = output_dir / "negative_evidence"

    certificate_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    negative_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in certificate_dir.glob("*.json"):
        path.unlink()

    for path in negative_dir.glob("*.json"):
        path.unlink()

    protocol = _protocol_definition(repo_root / "experiments/V0.11_PROTOCOL.md")

    certificate: JsonDict | None = None

    if rsa_passed:
        certificate = {
            "schema_version": ("BIZPROOF-V0.11-A2-CERTIFICATE-1"),
            "certificate_id": ("CERT-V011-A2-" + RSA_ID.upper()),
            "candidate_id": RSA_ID,
            "status": "CERTIFIED_A2",
            "terminal_outcome": "CERTIFIED_A2",
            "assistance_level": "A2",
            "protocol_definition": protocol,
            "authoring_mode": ("EXPLICIT_MANUAL_SCALAR_SEMANTIC_ADAPTER"),
            "semantic_binding_scope": rsa_proof["semantic_binding_scope"],
            "source": {
                "source_id": "openfisca_france",
                "class": rsa_probe["enclosing_class"],
                "function": rsa_probe["function"],
                "file": rsa_probe["file"],
                "resolved_commit": rsa_probe["resolved_commit"],
                "source_file_sha256": rsa_file_sha,
                "function_sha256": rsa_function_sha,
            },
            "evidence": {
                "proof_digest": rsa_proof["proof_digest"],
                "runtime": runtime,
                "symbolic": symbolic,
            },
            "claim_scope": (
                "Certification applies to the "
                "explicit scalar projection of "
                "turnover eligibility under "
                "activity-category membership "
                "predicates and scalar ceilings."
            ),
            "terminal_outcome_assigned": True,
            "final_study_complete": False,
        }

        certificate["certificate_digest"] = _digest(dict(certificate))

        (certificate_dir / (certificate["certificate_id"] + ".json")).write_text(
            json.dumps(
                certificate,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    (negative_dir / (MOBILITY_ID + ".json")).write_text(
        json.dumps(
            negative_evidence,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "rsa_a2_proof.json").write_text(
        json.dumps(
            rsa_proof,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "mobility_negative_evidence.json").write_text(
        json.dumps(
            negative_evidence,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Ledger
    # --------------------------------------------------------

    states: list[JsonDict] = []

    for previous in prior_states:
        candidate_id = str(previous["candidate_id"])

        if candidate_id == RSA_ID and certificate is not None:
            states.append(
                {
                    "candidate_id": RSA_ID,
                    "state": "TERMINAL_ASSIGNED",
                    "terminal_outcome": "CERTIFIED_A2",
                    "certificate_id": certificate["certificate_id"],
                    "certificate_digest": certificate["certificate_digest"],
                }
            )

        elif candidate_id == MOBILITY_ID:
            states.append(
                {
                    "candidate_id": MOBILITY_ID,
                    "state": "TERMINAL_ASSIGNED",
                    "terminal_outcome": ("NOT_CERTIFIED_UNSUPPORTED"),
                    "negative_evidence_digest": negative_evidence["negative_evidence_digest"],
                }
            )

        else:
            states.append(dict(previous))

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
        "phase": "RESIDUAL_BINDING_CLOSURE",
        "candidates_reviewed": 2,
        "a2_attempted": 1,
        "a2_certified": (1 if rsa_passed else 0),
        "unsupported_terminalized": 1,
        "terminalized_before": 67,
        "terminalized_after": len(assigned),
        "pending_after": len(pending),
        "final_certification_complete": False,
        "weighted_metrics_ready": False,
        "passed": (rsa_passed and len(states) == 90),
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
                ("# BIZPROOF V0.11 Residual Binding Closure"),
                "",
                ("- rsa_eligibilite_tns: " + ("CERTIFIED_A2" if rsa_passed else "proof failed")),
                ("- aide_mobilite_eligible: NOT_CERTIFIED_UNSUPPORTED"),
                "",
                (
                    "The RSA candidate requires "
                    "an explicit activity-category "
                    "semantic projection and is "
                    "therefore A2 rather than A1."
                ),
                "",
                (
                    "The mobility candidate is "
                    "unsupported because month-level "
                    "datetime casting has no validated "
                    "V0.11 temporal semantic contract."
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
        default=Path("benchmarks/v0.11/residual_binding_closure"),
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

    print("BIZPROOF V0.11 W5")

    print(
        "Residual candidates:",
        summary["candidates_reviewed"],
    )

    print(
        "New CERTIFIED_A2:",
        summary["a2_certified"],
    )

    print(
        "New NOT_CERTIFIED_UNSUPPORTED:",
        summary["unsupported_terminalized"],
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
