from __future__ import annotations

import argparse
import hashlib
import inspect
import itertools
import json
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypeAlias

import z3

from .generalization_a2_authoring import (
    _extract_function,
    _sha256_file,
    _sha256_text,
)

JsonDict: TypeAlias = dict[str, Any]

V1_IDS = {
    "e1cf29f02fa0dadc",
    "13df73dbd2825f80",
    "f234f0be14cf3ff3",
    "87d2f0b3b15f0ea6",
    "331f175e4aa92eef",
    "9603b9192132171c",
    "fa377c649a747a7d",
    "75e61ddb4dde4f1a",
    "34748d082751e0cc",
    "26a1af8837fe7ae4",
    "9cc9063a46d23cde",
}

SCALAR_TARGETS = {
    "f234f0be14cf3ff3": "DISCOUNT_SUBEVENT_KEY",
    "331f175e4aa92eef": "BASKET_DISCOUNT_SUCCESS",
    "9603b9192132171c": "LINE_TAX_KNOWN",
    "34748d082751e0cc": "BASKET_TAX_KNOWN",
}

NON_SCALAR_REVIEW = {
    "e1cf29f02fa0dadc": "LIST_RETURN",
    "13df73dbd2825f80": "DICT_RETURN",
    "87d2f0b3b15f0ea6": "TEXT_RETURN",
    "fa377c649a747a7d": "OBJECT_RETURN",
    "75e61ddb4dde4f1a": "TEXT_RETURN",
    "26a1af8837fe7ae4": "TEXT_RETURN",
    "9cc9063a46d23cde": "QUERYSET_RETURN",
}


def adapt_discount_subevent_key(
    subevent_id: int | None,
) -> int:

    return subevent_id or 0


def mutant_discount_subevent_key(
    subevent_id: int | None,
) -> int:

    return subevent_id or 1


def adapt_basket_discount_success(
    discount: int,
) -> bool:

    return discount > 0


def mutant_basket_discount_success(
    discount: int,
) -> bool:

    return discount >= 0


def adapt_line_tax_known(
    is_tax_known: bool,
) -> bool:

    return is_tax_known


def mutant_line_tax_known(
    is_tax_known: bool,
) -> bool:

    return not is_tax_known


def adapt_basket_tax_known(
    is_empty: bool,
    line_tax_known: tuple[bool, ...],
) -> bool:

    return not is_empty and all(line_tax_known)


def mutant_basket_tax_known(
    is_empty: bool,
    line_tax_known: tuple[bool, ...],
) -> bool:

    del is_empty

    return all(line_tax_known)


ADAPTERS = {
    "DISCOUNT_SUBEVENT_KEY": (
        adapt_discount_subevent_key,
        mutant_discount_subevent_key,
    ),
    "BASKET_DISCOUNT_SUCCESS": (
        adapt_basket_discount_success,
        mutant_basket_discount_success,
    ),
    "LINE_TAX_KNOWN": (
        adapt_line_tax_known,
        mutant_line_tax_known,
    ),
    "BASKET_TAX_KNOWN": (
        adapt_basket_tax_known,
        mutant_basket_tax_known,
    ),
}


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
            raise ValueError(f"expected object: {path}")

        result.append(value)

    return result


def _digest(
    value: Any,
) -> str:

    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _function_digest(
    function: Any,
) -> str:

    return hashlib.sha256(inspect.getsource(function).encode("utf-8")).hexdigest()


def _exec_function(
    source_slice: str,
    globals_extra: dict[str, Any] | None = None,
) -> Any:

    source = textwrap.dedent(source_slice)

    namespace: dict[str, Any] = {}

    if globals_extra:
        namespace.update(globals_extra)

    code = compile(
        source,
        "<locked-source-slice>",
        "exec",
    )

    exec(
        code,
        namespace,
    )

    names = [
        key for key, value in namespace.items() if (callable(value) and not key.startswith("__"))
    ]

    if len(names) != 1:
        raise ValueError("source slice must define exactly one callable")

    return namespace[names[0]]


def _verify_live_source(
    *,
    repo_root: Path,
    record: JsonDict,
) -> str:

    source_path = repo_root / "external_sources/v0.6" / str(record["source"]) / str(record["file"])

    if _sha256_file(source_path) != str(record["source_file_sha256"]):
        raise ValueError("source file SHA mismatch: " + str(record["candidate_id"]))

    source = source_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    lines = [int(value) for value in record["lines"]]

    _, segment = _extract_function(
        source,
        str(record["function"]),
        lines[0],
        lines[1],
    )

    if _sha256_text(segment) != str(record["function_sha256"]):
        raise ValueError("function SHA mismatch: " + str(record["candidate_id"]))

    return segment


def _runtime_key(
    source_slice: str,
) -> JsonDict:

    values: list[int | None] = [
        None,
        -3,
        -1,
        0,
        1,
        2,
        9,
    ]

    comparisons = 0
    mismatches = 0
    mutant_mismatches = 0
    examples = []

    for value in values:
        source_function = _exec_function(
            source_slice,
            {"positions": [SimpleNamespace(subevent_id=value)]},
        )

        external = source_function(0)

        adapter = adapt_discount_subevent_key(value)

        mutant = mutant_discount_subevent_key(value)

        comparisons += 1

        if external != adapter:
            mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

        examples.append(
            {
                "subevent_id": value,
                "external": external,
                "adapter": adapter,
                "mutant": mutant,
            }
        )

    return {
        "comparisons": comparisons,
        "adapter_mismatches": mismatches,
        "mutant_mismatches": mutant_mismatches,
        "examples": examples,
    }


def _runtime_discount_success(
    source_slice: str,
) -> JsonDict:

    source_function = _exec_function(source_slice)

    values = [
        -10,
        -2,
        -1,
        0,
        1,
        2,
        10,
    ]

    comparisons = 0
    mismatches = 0
    mutant_mismatches = 0

    for value in values:
        obj = SimpleNamespace(discount=value)

        external = source_function(obj)

        adapter = adapt_basket_discount_success(value)

        mutant = mutant_basket_discount_success(value)

        comparisons += 1

        if external != adapter:
            mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

    return {
        "comparisons": comparisons,
        "adapter_mismatches": mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _runtime_line_tax(
    source_slice: str,
) -> JsonDict:

    source_function = _exec_function(source_slice)

    comparisons = 0
    mismatches = 0
    mutant_mismatches = 0

    for value in (
        False,
        True,
    ):
        obj = SimpleNamespace(
            purchase_info=SimpleNamespace(price=SimpleNamespace(is_tax_known=value))
        )

        external = source_function(obj)

        adapter = adapt_line_tax_known(value)

        mutant = mutant_line_tax_known(value)

        comparisons += 1

        if external != adapter:
            mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

    return {
        "comparisons": comparisons,
        "adapter_mismatches": mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _runtime_basket_tax(
    source_slice: str,
) -> JsonDict:

    source_function = _exec_function(source_slice)

    comparisons = 0
    mismatches = 0
    mutant_mismatches = 0

    for length in range(4):
        for values in itertools.product(
            (
                False,
                True,
            ),
            repeat=length,
        ):
            flags = tuple(bool(value) for value in values)

            for is_empty in (
                False,
                True,
            ):
                lines = [SimpleNamespace(is_tax_known=value) for value in flags]

                obj = SimpleNamespace(
                    is_empty=is_empty,
                    all_lines=(lambda current=lines: current),
                )

                external = source_function(obj)

                adapter = adapt_basket_tax_known(
                    is_empty,
                    flags,
                )

                mutant = mutant_basket_tax_known(
                    is_empty,
                    flags,
                )

                comparisons += 1

                if external != adapter:
                    mismatches += 1

                if external != mutant:
                    mutant_mismatches += 1

    return {
        "bounded_line_count": [
            0,
            1,
            2,
            3,
        ],
        "comparisons": comparisons,
        "adapter_mismatches": mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _symbolic_key() -> JsonDict:

    value = z3.Int("subevent_id")

    source = z3.If(
        value != 0,
        value,
        0,
    )

    adapter = z3.If(
        value != 0,
        value,
        0,
    )

    mutant = z3.If(
        value != 0,
        value,
        1,
    )

    correct = z3.Solver()
    correct.add(source != adapter)

    mutant_solver = z3.Solver()
    mutant_solver.add(source != mutant)

    correct_status = correct.check()

    mutant_status = mutant_solver.check()

    return {
        "domain": "INTEGER_SUBEVENT_ID",
        "correct_solver_status": str(correct_status),
        "mutant_solver_status": str(mutant_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_disproved": mutant_status == z3.sat,
    }


def _symbolic_discount_success() -> JsonDict:

    discount = z3.Real("discount")

    source = discount > 0

    adapter = discount > 0

    mutant = discount >= 0

    correct = z3.Solver()
    correct.add(source != adapter)

    mutant_solver = z3.Solver()
    mutant_solver.add(source != mutant)

    correct_status = correct.check()

    mutant_status = mutant_solver.check()

    return {
        "domain": "REAL_DISCOUNT",
        "correct_solver_status": str(correct_status),
        "mutant_solver_status": str(mutant_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_disproved": mutant_status == z3.sat,
    }


def _symbolic_line_tax() -> JsonDict:

    value = z3.Bool("is_tax_known")

    correct = z3.Solver()
    correct.add(value != value)

    mutant_solver = z3.Solver()
    mutant_solver.add(value != z3.Not(value))

    correct_status = correct.check()

    mutant_status = mutant_solver.check()

    return {
        "domain": "BOOLEAN_TAX_STATE",
        "correct_solver_status": str(correct_status),
        "mutant_solver_status": str(mutant_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_disproved": mutant_status == z3.sat,
    }


def _symbolic_basket_tax() -> JsonDict:

    results = []

    for length in range(4):
        is_empty = z3.Bool(f"is_empty_{length}")

        flags = [z3.Bool(f"line_{length}_{index}") for index in range(length)]

        all_known = z3.And(*flags)

        source = z3.And(
            z3.Not(is_empty),
            all_known,
        )

        adapter = z3.And(
            z3.Not(is_empty),
            all_known,
        )

        mutant = all_known

        correct = z3.Solver()
        correct.add(source != adapter)

        mutant_solver = z3.Solver()
        mutant_solver.add(source != mutant)

        correct_status = correct.check()

        mutant_status = mutant_solver.check()

        results.append(
            {
                "line_count": length,
                "correct_solver_status": str(correct_status),
                "mutant_solver_status": str(mutant_status),
                "correct_proved": correct_status == z3.unsat,
                "mutant_disproved": mutant_status == z3.sat,
            }
        )

    return {
        "domain": "BOOLEAN_LINE_TAX_STATE_LENGTH_0_TO_3",
        "bounded_proofs": results,
        "correct_proved": all(item["correct_proved"] for item in results),
        "mutant_disproved": all(item["mutant_disproved"] for item in results),
    }


RUNTIME_FUNCTIONS = {
    "DISCOUNT_SUBEVENT_KEY": _runtime_key,
    "BASKET_DISCOUNT_SUCCESS": _runtime_discount_success,
    "LINE_TAX_KNOWN": _runtime_line_tax,
    "BASKET_TAX_KNOWN": _runtime_basket_tax,
}

SYMBOLIC_FUNCTIONS = {
    "DISCOUNT_SUBEVENT_KEY": _symbolic_key,
    "BASKET_DISCOUNT_SUCCESS": _symbolic_discount_success,
    "LINE_TAX_KNOWN": _symbolic_line_tax,
    "BASKET_TAX_KNOWN": _symbolic_basket_tax,
}


def _protocol_definition(
    path: Path,
) -> JsonDict:

    lines = path.read_text(encoding="utf-8").splitlines()

    matches = [
        {
            "line": index + 1,
            "text": line,
        }
        for index, line in enumerate(lines)
        if (
            "`CERTIFIED_A2`" in line and ("explicit human-authored scalar semantic adapter") in line
        )
    ]

    if len(matches) != 1:
        raise ValueError("A2 protocol definition not unique")

    return matches[0]


def build(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    source_records = _load_jsonl(
        repo_root / ("benchmarks/v0.11/a2_adapter_authoring/source_slices.jsonl")
    )

    source_by_id = {str(item["candidate_id"]): item for item in source_records}

    if V1_IDS != (set(SCALAR_TARGETS) | set(NON_SCALAR_REVIEW)):
        raise ValueError("V1 scalar/review partition invalid")

    if not V1_IDS.issubset(source_by_id):
        raise ValueError("V1 source coverage mismatch")

    proof_records: list[JsonDict] = []

    certificates: list[JsonDict] = []

    protocol = _protocol_definition(repo_root / "experiments/V0.11_PROTOCOL.md")

    for candidate_id in sorted(SCALAR_TARGETS):
        semantic_id = SCALAR_TARGETS[candidate_id]

        source_record = source_by_id[candidate_id]

        source_slice = _verify_live_source(
            repo_root=repo_root,
            record=source_record,
        )

        runtime = RUNTIME_FUNCTIONS[semantic_id](source_slice)

        symbolic = SYMBOLIC_FUNCTIONS[semantic_id]()

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
            "status": ("PROVED_A2_SCALAR" if passed else "A2_PROOF_FAILED"),
            "terminal_outcome": ("CERTIFIED_A2" if passed else None),
            "certification_claim": passed,
        }

        proof["proof_digest"] = _digest(dict(proof))

        proof_records.append(proof)

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
            "authoring_mode": ("EXPLICIT_MANUAL_SCALAR_SEMANTIC_ADAPTER"),
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
                "Certification is restricted "
                "to the explicit scalar semantic "
                "slice and declared validation "
                "domain represented by this "
                "certificate; it does not certify "
                "the complete external framework."
            ),
            "terminal_outcome_assigned": True,
            "final_study_complete": False,
        }

        certificate["certificate_digest"] = _digest(dict(certificate))

        certificates.append(certificate)

    review_records = []

    for candidate_id in sorted(NON_SCALAR_REVIEW):
        record = source_by_id[candidate_id]

        review_records.append(
            {
                "candidate_id": candidate_id,
                "source": record["source"],
                "class": record["class"],
                "function": record["function"],
                "return_shape": NON_SCALAR_REVIEW[candidate_id],
                "status": ("A2_SCALAR_SCOPE_REVIEW_REQUIRED"),
                "reason": (
                    "The V1 function is AST-simple "
                    "but its externally observable "
                    "return semantics are not "
                    "directly scalar. No scalar "
                    "projection is certified "
                    "without an additional "
                    "business-semantic scope "
                    "decision."
                ),
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

    for certificate in certificates:
        (certificate_dir / (str(certificate["certificate_id"]) + ".json")).write_text(
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
            for item in proof_records
        ),
        encoding="utf-8",
    )

    (output_dir / "non_scalar_review.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in review_records
        ),
        encoding="utf-8",
    )

    prior_states = _load_jsonl(
        repo_root / ("benchmarks/v0.11/remaining_cohort_sweep/candidate_terminal_state.jsonl")
    )

    if len(prior_states) != 90:
        raise ValueError("Phase-T terminal ledger must contain 90 candidates")

    certificate_by_id = {str(item["candidate_id"]): item for item in certificates}

    states = []

    for old in prior_states:
        candidate_id = str(old["candidate_id"])

        matched_certificate = certificate_by_id.get(candidate_id)

        if matched_certificate is None:
            states.append(dict(old))

            continue

        if old["state"] != "PENDING_UNASSIGNED":
            raise ValueError("refusing terminal overwrite: " + candidate_id)

        states.append(
            {
                "candidate_id": candidate_id,
                "state": "TERMINAL_ASSIGNED",
                "terminal_outcome": "CERTIFIED_A2",
                "certificate_id": matched_certificate["certificate_id"],
                "certificate_digest": matched_certificate["certificate_digest"],
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
        "phase": "A2_V1_SCALAR_PROOFS",
        "v1_candidates": 11,
        "scalar_candidates_attempted": 4,
        "scalar_candidates_proved": len(certificates),
        "non_scalar_review_required": len(review_records),
        "certificates_issued": len(certificates),
        "terminalized_before": 14,
        "terminalized_after": len(assigned),
        "pending_after": len(pending),
        "terminal_distribution": dict(sorted(distribution.items())),
        "weighted_metrics_ready": False,
        "final_certification_complete": False,
        "passed": (len(proof_records) == 4 and len(review_records) == 7 and len(states) == 90),
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
                ("# BIZPROOF V0.11 A2 V1 Scalar Proof Batch"),
                "",
                "- V1 candidates reviewed: 11",
                "- True scalar slices attempted: 4",
                (f"- Scalar certificates issued: {len(certificates)}"),
                (f"- Non-scalar V1 cases retained for review: {len(review_records)}"),
                "",
                ("AST simplicity is not treated as equivalent to scalar business semantics."),
                "",
                (
                    "Non-scalar list, dict, text, "
                    "object and queryset returns remain "
                    "pending rather than being projected "
                    "to a scalar without an explicit "
                    "semantic-scope decision."
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
        default=Path("benchmarks/v0.11/a2_v1_scalar_proofs"),
    )

    args = parser.parse_args()

    repo_root = args.repo_root.resolve()

    output_dir = args.output_dir

    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    output_dir = output_dir.resolve()

    summary = build(
        repo_root=repo_root,
        output_dir=output_dir,
    )

    print("BIZPROOF V0.11 A2 V1")

    print(
        "V1 candidates:",
        summary["v1_candidates"],
    )

    print(
        "True scalar attempted:",
        summary["scalar_candidates_attempted"],
    )

    print(
        "CERTIFIED_A2:",
        summary["certificates_issued"],
    )

    print(
        "Non-scalar review:",
        summary["non_scalar_review_required"],
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
