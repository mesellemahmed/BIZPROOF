from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, TypeAlias

from .generalization_candidate_proof import (
    _normalise_cohort_record,
)

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_CANDIDATES = 33
EXPECTED_FAMILIES = 30

EXPECTED_SOURCE_COUNTS = {
    "django_oscar": 15,
    "openfisca_france": 5,
    "pretix": 13,
}

EXPECTED_COMPLEXITY_COUNTS = {
    "HIGH": 15,
    "LOW": 4,
    "MEDIUM": 14,
}


def _load_json(
    path: Path,
) -> Any:

    return json.loads(path.read_text(encoding="utf-8"))


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


def _sha256_bytes(
    value: bytes,
) -> str:

    return hashlib.sha256(value).hexdigest()


def _sha256_text(
    value: str,
) -> str:

    return _sha256_bytes(value.encode("utf-8"))


def _sha256_file(
    path: Path,
) -> str:

    return _sha256_bytes(path.read_bytes())


def _canonical_digest(
    value: Any,
) -> str:

    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return _sha256_text(canonical)


def _verify_checkout_manifest(
    path: Path,
) -> dict[str, str]:

    value = _load_json(path)

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError("checkout manifest must be object")

    expected_digest = str(value["manifest_digest"])

    payload = dict(value)

    del payload["manifest_digest"]

    actual_digest = _canonical_digest(payload)

    if actual_digest != expected_digest:
        raise ValueError("checkout manifest digest mismatch")

    if value.get("all_passed") is not True:
        raise ValueError("checkout manifest failed")

    records = value.get("records")

    if not isinstance(
        records,
        list,
    ):
        raise ValueError("checkout records missing")

    result: dict[str, str] = {}

    for item in records:
        if not isinstance(
            item,
            dict,
        ):
            raise ValueError("invalid checkout record")

        expected = str(item["expected_commit"])

        actual = str(item["actual_commit"])

        if item.get("passed") is not True or expected != actual:
            raise ValueError("checkout record mismatch")

        result[str(item["source_id"])] = expected

    return result


def _extract_function(
    source: str,
    function_name: str,
    line_start: int,
    line_end: int,
) -> tuple[
    ast.FunctionDef | ast.AsyncFunctionDef,
    str,
]:

    tree = ast.parse(source)

    matches: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        if node.name != function_name:
            continue

        actual_end = int(node.end_lineno or node.lineno)

        if int(node.lineno) == line_start and actual_end == line_end:
            matches.append(node)

    if len(matches) != 1:
        raise ValueError(
            "exact function lookup failed: "
            f"{function_name} "
            f"{line_start}:{line_end} "
            f"matches={len(matches)}"
        )

    node = matches[0]

    segment = (
        ast.get_source_segment(
            source,
            node,
        )
        or ""
    )

    if not segment:
        raise ValueError("source segment unavailable")

    return node, segment


def _without_docstring(
    body: list[ast.stmt],
) -> list[ast.stmt]:

    if (
        body
        and isinstance(
            body[0],
            ast.Expr,
        )
        and isinstance(
            body[0].value,
            ast.Constant,
        )
        and isinstance(
            body[0].value.value,
            str,
        )
    ):
        return body[1:]

    return body


def _shape(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:

    body = _without_docstring(list(node.body))

    if len(body) == 1 and isinstance(
        body[0],
        ast.Return,
    ):
        return "SIMPLE_RETURN_EXPRESSION"

    straight_types = (
        ast.Assign,
        ast.AnnAssign,
        ast.AugAssign,
        ast.Return,
    )

    if (
        body
        and all(
            isinstance(
                statement,
                straight_types,
            )
            for statement in body
        )
        and isinstance(
            body[-1],
            ast.Return,
        )
    ):
        return "STRAIGHT_LINE_ASSIGN_RETURN"

    complex_types = (
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.With,
        ast.AsyncWith,
        ast.Match,
        ast.Yield,
        ast.YieldFrom,
        ast.Await,
    )

    if any(
        isinstance(
            item,
            complex_types,
        )
        for item in ast.walk(node)
    ):
        return "COMPLEX_CONTROL_FLOW"

    if any(
        isinstance(
            item,
            (
                ast.If,
                ast.IfExp,
            ),
        )
        for item in ast.walk(node)
    ):
        return "BRANCHING"

    return "GENERAL_ADAPTER_REVIEW"


def _profile(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> JsonDict:

    counts = Counter(type(item).__name__ for item in ast.walk(node))

    calls = sorted(
        {
            ast.unparse(item.func)
            for item in ast.walk(node)
            if isinstance(
                item,
                ast.Call,
            )
        }
    )

    attributes = sorted(
        {
            ast.unparse(item)
            for item in ast.walk(node)
            if isinstance(
                item,
                ast.Attribute,
            )
        }
    )

    returns = [
        (None if item.value is None else ast.unparse(item.value))
        for item in ast.walk(node)
        if isinstance(
            item,
            ast.Return,
        )
    ]

    body = _without_docstring(list(node.body))

    shape = _shape(node)

    if shape == "SIMPLE_RETURN_EXPRESSION":
        authoring_route = "V1_SCALAR_EXPRESSION"

    elif shape == "STRAIGHT_LINE_ASSIGN_RETURN":
        authoring_route = "V2_STRAIGHT_LINE"

    elif shape == "BRANCHING":
        authoring_route = "V3_BRANCHING"

    else:
        authoring_route = "V4_COMPLEX_MANUAL"

    return {
        "adapter_shape": shape,
        "authoring_route": authoring_route,
        "top_level_statements": [type(item).__name__ for item in body],
        "calls": calls,
        "attributes": attributes,
        "returns": returns,
        "node_counts": dict(sorted(counts.items())),
        "call_count": int(
            counts.get(
                "Call",
                0,
            )
        ),
        "branch_count": int(
            counts.get(
                "If",
                0,
            )
            + counts.get(
                "IfExp",
                0,
            )
        ),
        "loop_count": int(
            counts.get(
                "For",
                0,
            )
            + counts.get(
                "AsyncFor",
                0,
            )
            + counts.get(
                "While",
                0,
            )
        ),
    }


def _adapter_function_name(
    family_id: str,
) -> str:

    cleaned = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        family_id,
    ).strip("_")

    return "adapt_" + cleaned.lower()


def _family_rank(
    family: JsonDict,
) -> tuple[
    int,
    int,
    int,
    str,
]:

    route_rank = {
        "V1_SCALAR_EXPRESSION": 0,
        "V2_STRAIGHT_LINE": 1,
        "V3_BRANCHING": 2,
        "V4_COMPLEX_MANUAL": 3,
    }

    profiles = family["profiles"]

    max_route = max(route_rank[str(item["authoring_route"])] for item in profiles)

    max_branches = max(int(item["branch_count"]) for item in profiles)

    max_calls = max(int(item["call_count"]) for item in profiles)

    return (
        max_route,
        max_branches,
        max_calls,
        str(family["family_id"]),
    )


def build_pack(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    worklist = _load_jsonl(
        repo_root / ("benchmarks/v0.11/remaining_cohort_sweep/a2_worklist.jsonl")
    )

    if len(worklist) != 33:
        raise ValueError("A2 worklist is not 33")

    target_ids = {str(item["candidate_id"]) for item in worklist}

    families = _load_json(output_dir / "family_detection.json")

    if not isinstance(
        families,
        list,
    ):
        raise ValueError("family_detection is invalid")

    if len(families) != 30:
        raise ValueError("expected 30 A2 families")

    checkout = _verify_checkout_manifest(output_dir / "checkout_verification.json")

    cohort_records = [
        _normalise_cohort_record(item)
        for item in _load_jsonl(repo_root / ("benchmarks/v0.11/results/cohort.jsonl"))
    ]

    cohort = {
        str(item["candidate_id"]): item
        for item in cohort_records
        if (str(item["candidate_id"]) in target_ids)
    }

    if set(cohort) != target_ids:
        raise ValueError("cohort/A2 worklist mismatch")

    source_records: list[JsonDict] = []

    profiles: dict[
        str,
        JsonDict,
    ] = {}

    for candidate_id in sorted(target_ids):
        candidate = cohort[candidate_id]

        source_id = str(candidate["source"])

        source_file = str(candidate["file"])

        source_path = repo_root / "external_sources/v0.6" / source_id / source_file

        if not source_path.is_file():
            raise ValueError("source missing: " + str(source_path))

        actual_file_sha = _sha256_file(source_path)

        if actual_file_sha != str(candidate["source_file_sha256"]):
            raise ValueError("source SHA mismatch: " + candidate_id)

        source = source_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        lines = [int(value) for value in candidate["lines"]]

        node, segment = _extract_function(
            source,
            str(candidate["function"]),
            lines[0],
            lines[1],
        )

        actual_function_sha = _sha256_text(segment)

        if actual_function_sha != str(candidate["function_sha256"]):
            raise ValueError("function SHA mismatch: " + candidate_id)

        profile = _profile(node)

        profiles[candidate_id] = {
            "candidate_id": candidate_id,
            "source": source_id,
            "class": candidate["class"],
            "function": candidate["function"],
            "complexity": candidate["complexity"],
            "evidence": candidate["evidence"],
            **profile,
        }

        source_records.append(
            {
                "candidate_id": candidate_id,
                "source": source_id,
                "resolved_commit": checkout[source_id],
                "file": source_file,
                "class": candidate["class"],
                "function": candidate["function"],
                "lines": lines,
                "source_file_sha256": actual_file_sha,
                "function_sha256": actual_function_sha,
                "complexity": candidate["complexity"],
                "evidence": candidate["evidence"],
                "source_slice": segment,
                "profile": profile,
            }
        )

    source_counts = Counter(str(item["source"]) for item in source_records)

    complexity_counts = Counter(str(item["complexity"]) for item in source_records)

    if dict(source_counts) != EXPECTED_SOURCE_COUNTS:
        raise ValueError("source distribution changed")

    if dict(complexity_counts) != EXPECTED_COMPLEXITY_COUNTS:
        raise ValueError("complexity distribution changed")

    family_profiles: list[JsonDict] = []

    family_coverage: set[str] = set()

    for raw_family in families:
        if not isinstance(
            raw_family,
            dict,
        ):
            raise ValueError("invalid family")

        family_id = str(raw_family["family_id"])

        candidate_ids = [str(value) for value in raw_family["candidate_ids"]]

        family_coverage.update(candidate_ids)

        member_profiles = [profiles[candidate_id] for candidate_id in candidate_ids]

        routes = sorted({str(item["authoring_route"]) for item in member_profiles})

        family_profiles.append(
            {
                "family_id": family_id,
                "adapter_function": _adapter_function_name(family_id),
                "candidate_count": len(candidate_ids),
                "candidate_ids": candidate_ids,
                "sources": sorted({str(item["source"]) for item in member_profiles}),
                "complexities": sorted({str(item["complexity"]) for item in member_profiles}),
                "authoring_routes": routes,
                "profiles": member_profiles,
                "status": "ADAPTER_NOT_YET_AUTHORED",
                "terminal_outcome": None,
                "certification_claim": False,
            }
        )

    if family_coverage != target_ids:
        raise ValueError("30-family candidate coverage mismatch")

    family_profiles.sort(key=_family_rank)

    queue: list[JsonDict] = []

    route_counts: Counter[str] = Counter()

    for priority, family in enumerate(
        family_profiles,
        start=1,
    ):
        route = max(
            (str(item["authoring_route"]) for item in family["profiles"]),
            key=lambda value: {
                "V1_SCALAR_EXPRESSION": 0,
                "V2_STRAIGHT_LINE": 1,
                "V3_BRANCHING": 2,
                "V4_COMPLEX_MANUAL": 3,
            }[value],
        )

        route_counts[route] += 1

        queue.append(
            {
                "priority": priority,
                "family_id": family["family_id"],
                "adapter_function": family["adapter_function"],
                "candidate_count": family["candidate_count"],
                "candidate_ids": family["candidate_ids"],
                "sources": family["sources"],
                "complexities": family["complexities"],
                "authoring_route": route,
                "required_obligations": [
                    ("EXPLICIT_HUMAN_AUTHORED_SCALAR_ADAPTER"),
                    ("SOURCE_EXECUTED_PRESERVATION"),
                    "MUTANT_SENSITIVITY",
                    "SYMBOLIC_EQUIVALENCE",
                    ("EVIDENCE_CARRYING_CERTIFICATE"),
                ],
                "terminal_outcome": None,
                "certification_claim": False,
            }
        )

    route_files = {
        "V1_SCALAR_EXPRESSION": "v_batch_1_scalar.jsonl",
        "V2_STRAIGHT_LINE": "v_batch_2_straight.jsonl",
        "V3_BRANCHING": "v_batch_3_branching.jsonl",
        "V4_COMPLEX_MANUAL": "v_batch_4_complex.jsonl",
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (output_dir / "source_slices.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in source_records
        ),
        encoding="utf-8",
    )

    (output_dir / "candidate_profiles.jsonl").write_text(
        "".join(
            json.dumps(
                profiles[candidate_id],
                sort_keys=True,
            )
            + "\n"
            for candidate_id in sorted(profiles)
        ),
        encoding="utf-8",
    )

    (output_dir / "family_profiles.json").write_text(
        json.dumps(
            family_profiles,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "authoring_queue.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in queue
        ),
        encoding="utf-8",
    )

    for (
        route,
        filename,
    ) in route_files.items():
        selected = [item for item in queue if (item["authoring_route"] == route)]

        (output_dir / filename).write_text(
            "".join(
                json.dumps(
                    item,
                    sort_keys=True,
                )
                + "\n"
                for item in selected
            ),
            encoding="utf-8",
        )

    stub_lines = [
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "",
        "# AUTO-GENERATED AUTHORING SCAFFOLD.",
        "# These functions are NOT certified adapters.",
        "# Phase V must replace each NotImplementedError",
        "# with an explicit reviewed scalar adapter.",
        "",
    ]

    for item in queue:
        function_name = str(item["adapter_function"])

        family_id = str(item["family_id"])

        ids = ", ".join(str(value) for value in item["candidate_ids"])

        stub_lines.extend(
            [
                (f"def {function_name}(*args: Any, **kwargs: Any) -> Any:"),
                (f'    """{family_id}; candidates: {ids}."""'),
                ("    raise NotImplementedError("),
                ('        "Phase V explicit semantic adapter required"'),
                "    )",
                "",
                "",
            ]
        )

    (output_dir / "adapter_stubs.py").write_text(
        "\n".join(stub_lines),
        encoding="utf-8",
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "A2_AUTHORING_PROFILE",
        "candidate_count": 33,
        "family_count": 30,
        "source_verified_candidates": 33,
        "source_counts": dict(sorted(source_counts.items())),
        "complexity_counts": dict(sorted(complexity_counts.items())),
        "authoring_route_family_counts": dict(sorted(route_counts.items())),
        "terminal_outcomes_assigned": 0,
        "terminalized_total": 14,
        "pending_total": 76,
        "certification_claim": False,
        "passed": True,
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
                ("# BIZPROOF V0.11 A2 Adapter Authoring Profile"),
                "",
                "- Candidates: 33",
                "- Families: 30",
                ("- Source/function SHA verification: 33/33"),
                "",
                ("The generated adapter_stubs.py contains authoring scaffolds only."),
                ("No stub is treated as an adapter and no A2 outcome is assigned."),
                "",
                (
                    "Families are ordered by observed "
                    "source-AST structure so Phase V "
                    "can implement and prove simpler "
                    "scalar adapters first."
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
        default=Path("benchmarks/v0.11/a2_adapter_authoring"),
    )

    args = parser.parse_args()

    repo_root = args.repo_root.resolve()

    output_dir = args.output_dir

    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    output_dir = output_dir.resolve()

    summary = build_pack(
        repo_root=repo_root,
        output_dir=output_dir,
    )

    print("BIZPROOF V0.11 A2 U2")

    print(
        "Candidates:",
        summary["candidate_count"],
    )

    print(
        "Families:",
        summary["family_count"],
    )

    print(
        "Source verified:",
        summary["source_verified_candidates"],
    )

    print(
        "Authoring routes:",
        summary["authoring_route_family_counts"],
    )

    print("Terminal outcomes assigned: 0")

    print("PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
