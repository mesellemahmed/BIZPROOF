from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import z3

from .generalization_a2_v3_proof import (
    JsonDict,
    _digest,
    _exec_function,
    _function_digest,
    _load_jsonl,
    _protocol_definition,
    _solver_result,
    _verify_live_source,
)

SCALAR_PROJECTION_TARGETS = {
    "f3ebe6cce422947e": "STOCK_PURCHASE_PERMISSION",
    "7013ce92618a1e33": "BASKET_QUANTITY_PERMISSION",
}


UNSUPPORTED_IDS = {
    # V1 non-scalar return semantics
    "13df73dbd2825f80",
    "26a1af8837fe7ae4",
    "75e61ddb4dde4f1a",
    "87d2f0b3b15f0ea6",
    "9cc9063a46d23cde",
    "e1cf29f02fa0dadc",
    "fa377c649a747a7d",
    # V2 non-scalar return semantics
    "4d7d61b18dde0ad5",
    "6d009b7961c5d116",
    "6fd8bd69c26e7954",
    "d285ecd86455b150",
    # V3 residual non-scalar / stateful semantics
    "0f73ae8d15cf3408",
    "1311d905af0ebcb5",
    "674ea6fd35fa6c39",
    "801278c4d91c2185",
    "8b3e90ca7b531556",
    "e8850260c2763222",
}


COMPLEX_SCALAR_PENDING = {
    "53abfcd7d20a9cd6",
    "7bc9603bfbda7dc9",
}


ORIGINAL_A2_REMAINDER = set(SCALAR_PROJECTION_TARGETS) | UNSUPPORTED_IDS | COMPLEX_SCALAR_PENDING


def adapt_stock_purchase_permission(
    num_available: int,
    quantity: int,
) -> bool:

    if num_available <= 0:
        return False

    if quantity > num_available:
        return False

    return True


def mutant_stock_purchase_permission(
    num_available: int,
    quantity: int,
) -> bool:

    if num_available <= 0:
        return False

    if quantity >= num_available:
        return False

    return True


def adapt_basket_quantity_permission(
    line_present: bool,
    first_line_permitted: bool,
    combined_line_permitted: bool,
    max_allowed: int | None,
    quantity: int,
) -> bool:

    if line_present:
        if not first_line_permitted:
            return False

        if not combined_line_permitted:
            return False

    if max_allowed is not None and quantity > max_allowed:
        return False

    return True


def mutant_basket_quantity_permission(
    line_present: bool,
    first_line_permitted: bool,
    combined_line_permitted: bool,
    max_allowed: int | None,
    quantity: int,
) -> bool:

    del combined_line_permitted

    if line_present and not first_line_permitted:
        return False

    if max_allowed is not None and quantity > max_allowed:
        return False

    return True


ADAPTERS = {
    "STOCK_PURCHASE_PERMISSION": (
        adapt_stock_purchase_permission,
        mutant_stock_purchase_permission,
    ),
    "BASKET_QUANTITY_PERMISSION": (
        adapt_basket_quantity_permission,
        mutant_basket_quantity_permission,
    ),
}


BINDING_SCOPE = {
    "STOCK_PURCHASE_PERMISSION": (
        "The scalar projection is the first boolean component "
        "of the locked `(permitted, reason)` return contract. "
        "The human-readable reason is explicitly outside this "
        "A2 scalar certificate."
    ),
    "BASKET_QUANTITY_PERMISSION": (
        "The scalar projection is the first boolean component "
        "of the locked `(allowed, reason)` return contract. "
        "The two downstream line-availability decisions are "
        "bound as explicit booleans and message text remains "
        "outside the A2 scalar certificate."
    ),
}


class _Availability:
    def __init__(
        self,
        *,
        first: bool,
        combined: bool,
        num_available: int = 10,
    ) -> None:

        self.results = [
            first,
            combined,
        ]

        self.index = 0

        self.num_available = num_available

    def is_purchase_permitted(
        self,
        quantity: int,
    ) -> tuple[bool, str]:

        del quantity

        if self.index >= len(self.results):
            raise AssertionError("unexpected availability call")

        result = self.results[self.index]

        self.index += 1

        return (
            result,
            ("" if result else "blocked"),
        )


class _BasketHarness:
    def __init__(
        self,
        *,
        max_allowed: int | None,
    ) -> None:

        self._max_allowed = max_allowed

    def max_allowed_quantity(
        self,
    ) -> tuple[
        int | None,
        int,
    ]:

        threshold = self._max_allowed if self._max_allowed is not None else 999

        return (
            self._max_allowed,
            threshold,
        )

    def basket_quantity(
        self,
        line: Any,
    ) -> int:

        del line

        return 2


def _identity_translation(
    value: str,
) -> str:

    return value


def _runtime_stock_permission(
    source_slice: str,
) -> JsonDict:

    function = _exec_function(
        source_slice,
        "is_purchase_permitted",
        {
            "_": _identity_translation,
        },
    )

    comparisons = 0
    adapter_mismatches = 0
    mutant_mismatches = 0

    for num_available in (
        -1,
        0,
        1,
        2,
        5,
    ):
        for quantity in (
            0,
            1,
            2,
            5,
            6,
        ):
            obj = SimpleNamespace(num_available=num_available)

            external_result = function(
                obj,
                quantity,
            )

            external = bool(external_result[0])

            adapter = adapt_stock_purchase_permission(
                num_available,
                quantity,
            )

            mutant = mutant_stock_purchase_permission(
                num_available,
                quantity,
            )

            comparisons += 1

            if external != adapter:
                adapter_mismatches += 1

            if external != mutant:
                mutant_mismatches += 1

    return {
        "projection": "return[0]",
        "validation_domain": ("num_available in {-1,0,1,2,5}; quantity in {0,1,2,5,6}"),
        "comparisons": comparisons,
        "adapter_mismatches": adapter_mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _runtime_basket_permission(
    source_slice: str,
) -> JsonDict:

    function = _exec_function(
        source_slice,
        "is_quantity_allowed",
        {
            "_": _identity_translation,
        },
    )

    comparisons = 0
    adapter_mismatches = 0
    mutant_mismatches = 0

    max_values: list[int | None] = [
        None,
        0,
        2,
        5,
    ]

    for line_present in (
        False,
        True,
    ):
        for first_permitted in (
            False,
            True,
        ):
            for combined_permitted in (
                False,
                True,
            ):
                for max_allowed in max_values:
                    for quantity in (
                        0,
                        1,
                        3,
                        6,
                    ):
                        basket = _BasketHarness(max_allowed=max_allowed)

                        line = None

                        if line_present:
                            availability = _Availability(
                                first=first_permitted,
                                combined=combined_permitted,
                            )

                            line = SimpleNamespace(
                                purchase_info=SimpleNamespace(availability=availability)
                            )

                        external_result = function(
                            basket,
                            quantity,
                            line,
                        )

                        external = bool(external_result[0])

                        adapter = adapt_basket_quantity_permission(
                            bool(line_present),
                            bool(first_permitted),
                            bool(combined_permitted),
                            max_allowed,
                            quantity,
                        )

                        mutant = mutant_basket_quantity_permission(
                            bool(line_present),
                            bool(first_permitted),
                            bool(combined_permitted),
                            max_allowed,
                            quantity,
                        )

                        comparisons += 1

                        if external != adapter:
                            adapter_mismatches += 1

                        if external != mutant:
                            mutant_mismatches += 1

    return {
        "projection": "return[0]",
        "validation_domain": (
            "line present/absent, first and combined "
            "availability decisions, optional max quantity, "
            "and bounded requested quantity"
        ),
        "comparisons": comparisons,
        "adapter_mismatches": adapter_mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _symbolic_stock_permission() -> JsonDict:

    available = z3.Int("num_available")

    quantity = z3.Int("quantity")

    source = z3.And(
        available > 0,
        quantity <= available,
    )

    adapter = z3.And(
        available > 0,
        quantity <= available,
    )

    mutant = z3.And(
        available > 0,
        quantity < available,
    )

    result = _solver_result(
        source,
        adapter,
        mutant,
    )

    result["symbolic_domain"] = "unrestricted integer availability and requested quantity"

    result["projection"] = "return[0]"

    return result


def _symbolic_basket_permission() -> JsonDict:

    line_present = z3.Bool("line_present")

    first_permitted = z3.Bool("first_permitted")

    combined_permitted = z3.Bool("combined_permitted")

    max_defined = z3.Bool("max_defined")

    quantity = z3.Int("quantity")

    max_allowed = z3.Int("max_allowed")

    line_condition = z3.Or(
        z3.Not(line_present),
        z3.And(
            first_permitted,
            combined_permitted,
        ),
    )

    max_condition = z3.Or(
        z3.Not(max_defined),
        quantity <= max_allowed,
    )

    source = z3.And(
        line_condition,
        max_condition,
    )

    adapter = z3.And(
        line_condition,
        max_condition,
    )

    mutant = z3.And(
        z3.Or(
            z3.Not(line_present),
            first_permitted,
        ),
        max_condition,
    )

    result = _solver_result(
        source,
        adapter,
        mutant,
    )

    result["symbolic_domain"] = (
        "boolean downstream permission predicates and optional integer maximum quantity"
    )

    result["projection"] = "return[0]"

    return result


RUNTIME = {
    "STOCK_PURCHASE_PERMISSION": _runtime_stock_permission,
    "BASKET_QUANTITY_PERMISSION": _runtime_basket_permission,
}


SYMBOLIC = {
    "STOCK_PURCHASE_PERMISSION": _symbolic_stock_permission,
    "BASKET_QUANTITY_PERMISSION": _symbolic_basket_permission,
}


def _load_review_evidence(
    repo_root: Path,
) -> dict[str, JsonDict]:

    paths = [
        (repo_root / ("benchmarks/v0.11/a2_v1_scalar_proofs/non_scalar_review.jsonl")),
        (repo_root / ("benchmarks/v0.11/a2_v2_straight_proofs/review.jsonl")),
        (repo_root / ("benchmarks/v0.11/a2_v3_branching_proofs/review.jsonl")),
    ]

    result: dict[
        str,
        JsonDict,
    ] = {}

    for path in paths:
        for record in _load_jsonl(path):
            candidate_id = str(record["candidate_id"])

            result[candidate_id] = record

    return result


def build(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    if len(ORIGINAL_A2_REMAINDER) != 21:
        raise ValueError("residual A2 accounting must equal 21")

    source_records = _load_jsonl(
        repo_root / ("benchmarks/v0.11/a2_adapter_authoring/source_slices.jsonl")
    )

    source_by_id = {str(item["candidate_id"]): item for item in source_records}

    review_evidence = _load_review_evidence(repo_root)

    protocol = _protocol_definition(repo_root / "experiments/V0.11_PROTOCOL.md")

    proofs: list[JsonDict] = []

    certificates: list[JsonDict] = []

    for candidate_id in sorted(SCALAR_PROJECTION_TARGETS):
        semantic_id = SCALAR_PROJECTION_TARGETS[candidate_id]

        source_record = source_by_id[candidate_id]

        source_slice = _verify_live_source(
            repo_root=repo_root,
            record=source_record,
        )

        runtime = RUNTIME[semantic_id](source_slice)

        symbolic = SYMBOLIC[semantic_id]()

        adapter, mutant = ADAPTERS[semantic_id]

        passed = (
            runtime["adapter_mismatches"] == 0
            and runtime["mutant_mismatches"] > 0
            and symbolic["correct_proved"] is True
            and symbolic["mutant_disproved"] is True
        )

        proof: JsonDict = {
            "candidate_id": candidate_id,
            "semantic_adapter": semantic_id,
            "projection": "return[0]",
            "semantic_binding_scope": BINDING_SCOPE[semantic_id],
            "source": source_record["source"],
            "class": source_record["class"],
            "function": source_record["function"],
            "source_file_sha256": source_record["source_file_sha256"],
            "function_sha256": source_record["function_sha256"],
            "adapter_function": adapter.__name__,
            "adapter_function_sha256": _function_digest(adapter),
            "mutant_function": mutant.__name__,
            "mutant_function_sha256": _function_digest(mutant),
            "runtime": runtime,
            "symbolic": symbolic,
            "status": ("PROVED_A2_SCALAR_PROJECTION" if passed else "A2_PROOF_FAILED"),
            "terminal_outcome": ("CERTIFIED_A2" if passed else None),
            "certification_claim": passed,
        }

        proof["proof_digest"] = _digest(dict(proof))

        proofs.append(proof)

        if not passed:
            continue

        certificate: JsonDict = {
            "schema_version": ("BIZPROOF-V0.11-A2-CERTIFICATE-1"),
            "certificate_id": ("CERT-V011-A2-" + candidate_id.upper()),
            "candidate_id": candidate_id,
            "status": "CERTIFIED_A2",
            "terminal_outcome": "CERTIFIED_A2",
            "assistance_level": "A2",
            "protocol_definition": protocol,
            "authoring_mode": ("EXPLICIT_MANUAL_SCALAR_SEMANTIC_PROJECTION"),
            "projection": "return[0]",
            "semantic_binding_scope": BINDING_SCOPE[semantic_id],
            "source": {
                "source_id": source_record["source"],
                "class": source_record["class"],
                "function": source_record["function"],
                "file": source_record["file"],
                "lines": source_record["lines"],
                "source_file_sha256": source_record["source_file_sha256"],
                "function_sha256": source_record["function_sha256"],
            },
            "adapter": {
                "semantic_adapter": semantic_id,
                "function": adapter.__name__,
                "function_sha256": proof["adapter_function_sha256"],
                "mutant_function": mutant.__name__,
                "mutant_function_sha256": proof["mutant_function_sha256"],
            },
            "evidence": {
                "proof_digest": proof["proof_digest"],
                "runtime": runtime,
                "symbolic": symbolic,
            },
            "claim_scope": (
                "Certification covers only the explicit "
                "first boolean component of the locked "
                "tuple return. Human-readable reason text "
                "and surrounding framework behavior are "
                "outside this certificate."
            ),
            "terminal_outcome_assigned": True,
            "final_study_complete": False,
        }

        certificate["certificate_digest"] = _digest(dict(certificate))

        certificates.append(certificate)

    unsupported_records: list[JsonDict] = []

    negative_dir = output_dir / "negative_evidence"

    negative_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for old_path in negative_dir.glob("*.json"):
        old_path.unlink()

    for candidate_id in sorted(UNSUPPORTED_IDS):
        source_record = source_by_id[candidate_id]

        review = review_evidence.get(
            candidate_id,
            {},
        )

        reason_code = (
            review.get("reason_code")
            or review.get("return_shape")
            or review.get("status")
            or "NO_SCALAR_A2_SCOPE"
        )

        prior_reason = review.get("reason") or (
            "The reviewed source does not "
            "provide a defensible single scalar "
            "business-semantic projection under "
            "the frozen V0.11 A2 protocol."
        )

        evidence: JsonDict = {
            "schema_version": ("BIZPROOF-V0.11-NEGATIVE-EVIDENCE-1"),
            "candidate_id": candidate_id,
            "terminal_outcome": "NOT_CERTIFIED_UNSUPPORTED",
            "scope": ("V0.11 A2 explicit scalar semantic adapter"),
            "reason_code": reason_code,
            "reason": prior_reason,
            "interpretation": (
                "Unsupported means unsupported by "
                "the frozen A2 scalar certification "
                "scope. It does not claim that the "
                "external function is intrinsically "
                "unverifiable by another formalism."
            ),
            "source": {
                "source_id": source_record["source"],
                "class": source_record["class"],
                "function": source_record["function"],
                "file": source_record["file"],
                "lines": source_record["lines"],
                "source_file_sha256": source_record["source_file_sha256"],
                "function_sha256": source_record["function_sha256"],
            },
            "prior_review": review,
            "certification_claim": False,
        }

        evidence["negative_evidence_digest"] = _digest(dict(evidence))

        (negative_dir / (candidate_id + ".json")).write_text(
            json.dumps(
                evidence,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        unsupported_records.append(evidence)

    complex_pending_records = []

    for candidate_id in sorted(COMPLEX_SCALAR_PENDING):
        source_record = source_by_id[candidate_id]

        review = review_evidence[candidate_id]

        complex_pending_records.append(
            {
                "candidate_id": candidate_id,
                "source": source_record["source"],
                "class": source_record["class"],
                "function": source_record["function"],
                "reason": review.get("reason"),
                "reason_code": review.get("reason_code"),
                "status": ("A2_COMPLEX_SCALAR_MAPPING_PENDING"),
                "terminal_outcome": None,
                "certification_claim": False,
            }
        )

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

    for certificate_record in certificates:
        (certificate_dir / (str(certificate_record["certificate_id"]) + ".json")).write_text(
            json.dumps(
                certificate_record,
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

    (output_dir / "unsupported.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in unsupported_records
        ),
        encoding="utf-8",
    )

    (output_dir / "complex_scalar_pending.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in complex_pending_records
        ),
        encoding="utf-8",
    )

    prior_states = _load_jsonl(
        repo_root / ("benchmarks/v0.11/a2_v3_branching_proofs/candidate_terminal_state.jsonl")
    )

    if len(prior_states) != 90:
        raise ValueError("V3 ledger must contain 90 candidates")

    certificate_by_id = {str(item["candidate_id"]): item for item in certificates}

    negative_by_id = {str(item["candidate_id"]): item for item in unsupported_records}

    states: list[JsonDict] = []

    for previous_state in prior_states:
        candidate_id = str(previous_state["candidate_id"])

        matched_certificate = certificate_by_id.get(candidate_id)

        negative = negative_by_id.get(candidate_id)

        if matched_certificate is None and negative is None:
            states.append(dict(previous_state))

            continue

        if previous_state["state"] != "PENDING_UNASSIGNED":
            raise ValueError("refusing terminal overwrite: " + candidate_id)

        if matched_certificate is not None:
            states.append(
                {
                    "candidate_id": candidate_id,
                    "state": "TERMINAL_ASSIGNED",
                    "terminal_outcome": "CERTIFIED_A2",
                    "certificate_id": matched_certificate["certificate_id"],
                    "certificate_digest": matched_certificate["certificate_digest"],
                }
            )

        else:
            assert negative is not None

            states.append(
                {
                    "candidate_id": candidate_id,
                    "state": "TERMINAL_ASSIGNED",
                    "terminal_outcome": ("NOT_CERTIFIED_UNSUPPORTED"),
                    "negative_evidence_digest": negative["negative_evidence_digest"],
                }
            )

    assigned = [item for item in states if (item["state"] == "TERMINAL_ASSIGNED")]

    pending = [item for item in states if (item["state"] == "PENDING_UNASSIGNED")]

    distribution: dict[
        str,
        int,
    ] = {}

    for item in assigned:
        outcome = str(item["terminal_outcome"])

        distribution[outcome] = (
            distribution.get(
                outcome,
                0,
            )
            + 1
        )

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
        "phase": "A2_RESIDUAL_CLOSURE",
        "residual_a2_candidates": 21,
        "scalar_projections_attempted": 2,
        "scalar_projections_proved": len(certificates),
        "unsupported_terminalized": len(unsupported_records),
        "complex_scalar_pending": len(complex_pending_records),
        "terminalized_before": 26,
        "terminalized_after": len(assigned),
        "pending_after": len(pending),
        "terminal_distribution": dict(sorted(distribution.items())),
        "a2_remaining_worklist": [item["candidate_id"] for item in complex_pending_records],
        "weighted_metrics_ready": False,
        "final_certification_complete": False,
        "passed": (
            len(proofs) == 2
            and len(unsupported_records) == 17
            and len(complex_pending_records) == 2
            and len(states) == 90
        ),
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
                ("# BIZPROOF V0.11 Residual A2 Closure"),
                "",
                "- Residual A2 candidates: 21",
                "- Boolean tuple projections attempted: 2",
                (f"- New A2 certificates: {len(certificates)}"),
                (f"- NOT_CERTIFIED_UNSUPPORTED: {len(unsupported_records)}"),
                "- Complex scalar mappings left pending: 2",
                "",
                (
                    "Unsupported classifications are "
                    "strictly relative to the frozen "
                    "V0.11 A2 scalar-adapter scope."
                ),
                "",
                (
                    "No claim is made that composite, "
                    "textual, temporal, object-valued or "
                    "side-effecting functions are "
                    "intrinsically unverifiable."
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
        default=Path("benchmarks/v0.11/a2_residual_closure"),
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

    print("BIZPROOF V0.11 A2 residual closure")

    print(
        "Residual A2:",
        summary["residual_a2_candidates"],
    )

    print(
        "Projection attempts:",
        summary["scalar_projections_attempted"],
    )

    print(
        "New CERTIFIED_A2:",
        summary["scalar_projections_proved"],
    )

    print(
        "Unsupported terminalized:",
        summary["unsupported_terminalized"],
    )

    print(
        "Complex scalar pending:",
        summary["complex_scalar_pending"],
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
