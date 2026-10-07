from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypeAlias

from .adapter_preservation import _checkout_commit

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_COHORT_SHA256 = "3144f973a166ebee41a059c538b81ffac5a5d15737982c6d95e59175325ca108"

EXPECTED_CANDIDATES = 36


SEMANTIC_CONTRACT_CLASSES = {
    "OPENFISCA_ENTITY_LOOKUP",
    "SEMANTIC_LIBRARY_PRIMITIVE",
    "EXTERNAL_CALL",
    "GLOBAL_CONSTANT",
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

    records: list[JsonDict] = []

    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = line.strip()

        if not line:
            continue

        value = json.loads(line)

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(f"record {number} in {path} is not an object")

        records.append(value)

    return records


def _sha256_bytes(
    value: bytes,
) -> str:

    return hashlib.sha256(value).hexdigest()


def _verify_locked_commits(
    *,
    lock_path: Path,
    external_root: Path,
) -> dict[str, str]:

    lock = _load_json(lock_path)

    raw_sources = lock.get("sources")

    if not isinstance(
        raw_sources,
        list,
    ):
        raise ValueError("LOCK sources must be a list")

    verified: dict[str, str] = {}

    for item in raw_sources:
        if not isinstance(
            item,
            dict,
        ):
            continue

        source_id = str(item["id"])

        expected = str(item["resolved_commit"])

        actual = _checkout_commit(external_root / source_id)

        if actual != expected:
            raise ValueError(
                f"external checkout mismatch for {source_id}: expected={expected}, actual={actual}"
            )

        verified[source_id] = actual

    return verified


def _module_import_evidence(
    tree: ast.Module,
    primitive: str,
) -> list[JsonDict]:

    evidence: list[JsonDict] = []

    for node in tree.body:
        if isinstance(
            node,
            ast.ImportFrom,
        ):
            module_name = node.module or ""

            for alias in node.names:
                if alias.name == "*":
                    evidence.append(
                        {
                            "evidence_kind": "WILDCARD_IMPORT",
                            "module": module_name,
                            "line": int(node.lineno),
                            "source": ast.unparse(node),
                        }
                    )

                    continue

                local_name = alias.asname or alias.name

                if local_name == primitive:
                    evidence.append(
                        {
                            "evidence_kind": "EXPLICIT_IMPORT",
                            "module": module_name,
                            "imported_name": alias.name,
                            "local_name": local_name,
                            "line": int(node.lineno),
                            "source": ast.unparse(node),
                        }
                    )

        elif isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]

                if local_name == primitive:
                    evidence.append(
                        {
                            "evidence_kind": "MODULE_IMPORT",
                            "module": alias.name,
                            "local_name": local_name,
                            "line": int(node.lineno),
                            "source": ast.unparse(node),
                        }
                    )

    return evidence


def _module_definition_evidence(
    tree: ast.Module,
    primitive: str,
) -> list[JsonDict]:

    evidence: list[JsonDict] = []

    for node in tree.body:
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            if node.name == primitive:
                evidence.append(
                    {
                        "evidence_kind": "MODULE_DEFINITION",
                        "definition_type": type(node).__name__,
                        "line": int(node.lineno),
                        "source": ast.unparse(node).splitlines()[0],
                    }
                )

        elif isinstance(
            node,
            ast.Assign,
        ):
            names = [
                target.id
                for target in node.targets
                if isinstance(
                    target,
                    ast.Name,
                )
            ]

            if primitive in names:
                evidence.append(
                    {
                        "evidence_kind": "MODULE_ASSIGNMENT",
                        "line": int(node.lineno),
                        "source": ast.unparse(node),
                    }
                )

        elif isinstance(
            node,
            ast.AnnAssign,
        ):
            if (
                isinstance(
                    node.target,
                    ast.Name,
                )
                and node.target.id == primitive
            ):
                evidence.append(
                    {
                        "evidence_kind": "MODULE_ASSIGNMENT",
                        "line": int(node.lineno),
                        "source": ast.unparse(node),
                    }
                )

    return evidence


def _callable_root(
    expression: str,
) -> tuple[
    str | None,
    str,
]:

    try:
        node = ast.parse(
            expression,
            mode="eval",
        ).body

    except SyntaxError:
        return (
            None,
            "UNPARSEABLE",
        )

    if not isinstance(
        node,
        ast.Call,
    ):
        return (
            None,
            "NOT_CALL",
        )

    if isinstance(
        node.func,
        ast.Name,
    ):
        return (
            node.func.id,
            "NAME",
        )

    if isinstance(
        node.func,
        ast.Attribute,
    ):
        return (
            node.func.attr,
            "ATTRIBUTE",
        )

    return (
        None,
        type(node.func).__name__,
    )


def _attribute_root(
    expression: str,
) -> str | None:

    try:
        node = ast.parse(
            expression,
            mode="eval",
        ).body

    except SyntaxError:
        return None

    while isinstance(
        node,
        ast.Attribute,
    ):
        node = node.value

    if isinstance(
        node,
        ast.Name,
    ):
        return node.id

    if isinstance(
        node,
        ast.Call,
    ):
        if isinstance(
            node.func,
            ast.Name,
        ):
            return node.func.id

        if isinstance(
            node.func,
            ast.Attribute,
        ):
            return node.func.attr

    return None


def _occurrence_evidence(
    *,
    obligation: JsonDict,
    skeleton: JsonDict,
    source_tree: ast.Module,
) -> JsonDict:

    primitive = str(obligation["primitive"])

    kind = str(obligation["kind"])

    expression = str(obligation["source_expression"])

    parameters = {str(value) for value in skeleton["function_parameters"]}

    evidence: list[JsonDict] = []

    if kind == "CALL":
        callable_name, call_form = _callable_root(expression)

        if callable_name is not None and callable_name in parameters:
            evidence.append(
                {
                    "evidence_kind": "FUNCTION_PARAMETER_CALLABLE",
                    "parameter": callable_name,
                    "call_form": call_form,
                }
            )

        evidence.extend(
            _module_definition_evidence(
                source_tree,
                primitive,
            )
        )

        evidence.extend(
            _module_import_evidence(
                source_tree,
                primitive,
            )
        )

        if primitive in dir(builtins):
            evidence.append(
                {
                    "evidence_kind": "PYTHON_BUILTIN",
                    "primitive": primitive,
                }
            )

    elif kind == "GLOBAL_NAME":
        if primitive in parameters:
            evidence.append(
                {
                    "evidence_kind": "FUNCTION_PARAMETER_VALUE",
                    "parameter": primitive,
                }
            )

        evidence.extend(
            _module_definition_evidence(
                source_tree,
                primitive,
            )
        )

        evidence.extend(
            _module_import_evidence(
                source_tree,
                primitive,
            )
        )

    elif kind == "ATTRIBUTE":
        root = _attribute_root(expression)

        if root is not None and root in parameters:
            evidence.append(
                {
                    "evidence_kind": "PARAMETER_ATTRIBUTE_ACCESS",
                    "parameter": root,
                    "attribute": primitive,
                }
            )

        elif root is not None:
            evidence.append(
                {
                    "evidence_kind": "ATTRIBUTE_ROOT_CONTEXT",
                    "root": root,
                    "attribute": primitive,
                }
            )

    strong_kinds = {
        "FUNCTION_PARAMETER_CALLABLE",
        "FUNCTION_PARAMETER_VALUE",
        "EXPLICIT_IMPORT",
        "MODULE_IMPORT",
        "MODULE_DEFINITION",
        "MODULE_ASSIGNMENT",
        "PYTHON_BUILTIN",
    }

    if any(str(item["evidence_kind"]) in strong_kinds for item in evidence):
        status = "SOURCE_EVIDENCE_IDENTIFIED"

    elif any(str(item["evidence_kind"]) == "WILDCARD_IMPORT" for item in evidence):
        status = "SOURCE_EVIDENCE_PARTIAL"

    elif evidence:
        status = "CONTEXT_EVIDENCE_ONLY"

    else:
        status = "NO_SOURCE_EVIDENCE"

    return {
        "binding_id": str(obligation["binding_id"]),
        "kind": kind,
        "primitive": primitive,
        "family_class": str(obligation["family_class"]),
        "source_expression": expression,
        "context_inferred_type": str(obligation["inferred_type"]),
        "context_type_requirements": obligation["type_requirements"],
        "semantic_contract_required": (
            str(obligation["family_class"]) in SEMANTIC_CONTRACT_CLASSES
        ),
        "semantic_type": "UNRESOLVED",
        "semantic_definition_status": "UNRESOLVED",
        "evidence_status": status,
        "evidence": evidence,
    }


def build_semantic_evidence(
    *,
    contract_summary_path: Path,
    contract_skeletons_path: Path,
    binding_registry_path: Path,
    lock_path: Path,
    external_root: Path,
    output_dir: Path,
) -> JsonDict:

    contract_summary = _load_json(contract_summary_path)

    if str(contract_summary["cohort_sha256"]) != EXPECTED_COHORT_SHA256:
        raise ValueError("contract cohort digest mismatch")

    skeletons = _load_jsonl(contract_skeletons_path)

    if len(skeletons) != EXPECTED_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CANDIDATES} contract skeletons, got {len(skeletons)}")

    registry = _load_json(binding_registry_path)

    registry_entries = registry["entries"]

    verified_commits = _verify_locked_commits(
        lock_path=lock_path,
        external_root=external_root,
    )

    source_cache: dict[
        tuple[
            str,
            str,
        ],
        tuple[
            ast.Module,
            str,
        ],
    ] = {}

    occurrences: list[JsonDict] = []

    for skeleton in skeletons:
        source_id = str(skeleton["source_id"])

        relative_file = str(skeleton["file"])

        cache_key = (
            source_id,
            relative_file,
        )

        if cache_key not in source_cache:
            source_path = external_root / source_id / relative_file

            if not source_path.is_file():
                raise ValueError(f"source file missing: {source_path}")

            raw = source_path.read_bytes()

            source_text = raw.decode("utf-8")

            source_cache[cache_key] = (
                ast.parse(
                    source_text,
                    filename=str(source_path),
                ),
                _sha256_bytes(raw),
            )

        (
            source_tree,
            source_sha,
        ) = source_cache[cache_key]

        for obligation in skeleton["binding_obligations"]:
            evidence = _occurrence_evidence(
                obligation=obligation,
                skeleton=skeleton,
                source_tree=source_tree,
            )

            evidence.update(
                {
                    "candidate_id": str(skeleton["candidate_id"]),
                    "source_id": source_id,
                    "resolved_commit": verified_commits[source_id],
                    "file": relative_file,
                    "source_file_sha256": source_sha,
                    "function": str(skeleton["function"]),
                    "enclosing_class": skeleton["enclosing_class"],
                    "certification_claim": False,
                }
            )

            occurrences.append(evidence)

    by_registry_key: dict[
        tuple[
            str,
            str,
            str,
        ],
        list[JsonDict],
    ] = defaultdict(list)

    for occurrence in occurrences:
        registry_key = (
            str(occurrence["family_class"]),
            str(occurrence["kind"]),
            str(occurrence["primitive"]),
        )

        by_registry_key[registry_key].append(occurrence)

    semantic_entries: list[JsonDict] = []

    for registry_entry in registry_entries:
        registry_key = (
            str(registry_entry["family_class"]),
            str(registry_entry["kind"]),
            str(registry_entry["primitive"]),
        )

        related = by_registry_key.get(
            registry_key,
            [],
        )

        statuses = Counter(str(item["evidence_status"]) for item in related)

        contextual_types = sorted({str(item["context_inferred_type"]) for item in related})

        identified = statuses.get(
            "SOURCE_EVIDENCE_IDENTIFIED",
            0,
        )

        if related and identified == len(related):
            evidence_coverage = "COMPLETE"

        elif related:
            evidence_coverage = "PARTIAL"

        else:
            evidence_coverage = "NONE"

        requires_contract = str(registry_entry["family_class"]) in SEMANTIC_CONTRACT_CLASSES

        if requires_contract:
            next_action = "DEFINE_AND_VALIDATE_SEMANTIC_CONTRACT"

        elif evidence_coverage == "NONE":
            next_action = "SOURCE_REVIEW"

        else:
            next_action = "DEFINE_DOMAIN_AND_BINDING"

        semantic_entries.append(
            {
                "registry_id": str(registry_entry["registry_id"]),
                "family_class": str(registry_entry["family_class"]),
                "kind": str(registry_entry["kind"]),
                "primitive": str(registry_entry["primitive"]),
                "candidate_count": int(registry_entry["candidate_count"]),
                "occurrence_count": len(related),
                "contextual_types": contextual_types,
                "context_type_variation": (len(contextual_types) > 1),
                "semantic_type": "UNRESOLVED",
                "semantic_contract_required": requires_contract,
                "semantic_contract_status": "MISSING",
                "evidence_coverage": evidence_coverage,
                "evidence_status_counts": dict(sorted(statuses.items())),
                "next_action": next_action,
                "resolution_status": "UNRESOLVED",
                "certification_claim": False,
            }
        )

    semantic_entries.sort(
        key=lambda item: (
            0 if item["semantic_contract_required"] else 1,
            0 if item["context_type_variation"] else 1,
            -int(item["candidate_count"]),
            -int(item["occurrence_count"]),
            str(item["primitive"]),
        )
    )

    evidence_status_counts = Counter(str(item["evidence_status"]) for item in occurrences)

    semantic_contract_counts = Counter(
        str(item["family_class"]) for item in semantic_entries if item["semantic_contract_required"]
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "SEMANTIC_SOURCE_EVIDENCE",
        "cohort_sha256": EXPECTED_COHORT_SHA256,
        "contract_candidates": len(skeletons),
        "registry_entries": len(semantic_entries),
        "binding_occurrences": len(occurrences),
        "evidence_status_counts": dict(sorted(evidence_status_counts.items())),
        "semantic_contract_class_counts": dict(sorted(semantic_contract_counts.items())),
        "context_type_variation_entries": sum(
            1 for item in semantic_entries if item["context_type_variation"]
        ),
        "semantic_types_resolved": 0,
        "all_semantic_types_unresolved": all(
            item["semantic_type"] == "UNRESOLVED" for item in semantic_entries
        ),
        "certification_claim": False,
        "passed": (
            len(skeletons) == EXPECTED_CANDIDATES and len(semantic_entries) == len(registry_entries)
        ),
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (output_dir / "occurrence_evidence.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in occurrences
        ),
        encoding="utf-8",
    )

    (output_dir / "semantic_registry.json").write_text(
        json.dumps(
            {
                "benchmark_version": "0.11.0",
                "phase": "SEMANTIC_REGISTRY_UNRESOLVED",
                "cohort_sha256": EXPECTED_COHORT_SHA256,
                "entries": semantic_entries,
                "certification_claim": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
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

    report = [
        "# BIZPROOF V0.11 Semantic Source Evidence",
        "",
        ("This phase separates contextual type observations from source-backed semantic evidence."),
        "",
        ("No semantic type or binding meaning is inferred solely from usage context."),
        "",
        (f"- Contract candidates: {len(skeletons)}"),
        (f"- Registry entries: {len(semantic_entries)}"),
        (f"- Binding occurrences: {len(occurrences)}"),
        "- Semantic types resolved: 0",
        "",
        "## Evidence statuses",
        "",
    ]

    for (
        status_name,
        value,
    ) in sorted(evidence_status_counts.items()):
        report.append(f"- `{status_name}`: {value}")

    report.extend(
        [
            "",
            "## Scientific boundary",
            "",
            ("`context_inferred_type` is only a structural usage constraint."),
            "",
            (
                "`semantic_type` remains UNRESOLVED until an "
                "explicit source-backed semantic contract is "
                "defined and validated."
            ),
            "",
        ]
    )

    (output_dir / "REVIEWER_REPORT.md").write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    return summary


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--contract-summary",
        type=Path,
        default=Path("benchmarks/v0.11/contracts/summary.json"),
    )

    parser.add_argument(
        "--contract-skeletons",
        type=Path,
        default=Path("benchmarks/v0.11/contracts/contract_skeletons.jsonl"),
    )

    parser.add_argument(
        "--binding-registry",
        type=Path,
        default=Path("benchmarks/v0.11/contracts/binding_registry.json"),
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
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/semantic_evidence"),
    )

    args = parser.parse_args()

    summary = build_semantic_evidence(
        contract_summary_path=args.contract_summary,
        contract_skeletons_path=args.contract_skeletons,
        binding_registry_path=args.binding_registry,
        lock_path=args.lock,
        external_root=args.external_root,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 semantic source evidence")

    print(
        "Registry entries:",
        summary["registry_entries"],
    )

    print(
        "Binding occurrences:",
        summary["binding_occurrences"],
    )

    print(
        "Evidence statuses:",
        summary["evidence_status_counts"],
    )

    print(
        "Semantic types resolved:",
        summary["semantic_types_resolved"],
    )

    print("Certification claim: NO")

    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
