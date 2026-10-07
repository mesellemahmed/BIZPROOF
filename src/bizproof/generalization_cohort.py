from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]

EXPECTED_CANDIDATE_SHA256 = "a8a706aa831427478b1b3e96bd7a60800865436a28ead2367b2c4edcdae8871f"
EXPECTED_POOL_SHA256 = "33be87ff55ceb6ea0518a76dfcf0244fa4e103593cea2afb4cfb5dc2c9cc8ab3"
SELECTION_SEED = "BIZPROOF-V0.11-20260926"
PER_STRATUM = 10
EXPECTED_POOL_SIZE = 730
EXPECTED_CANDIDATE_COUNT = 1222

EXPECTED_STRATA: dict[tuple[str, str], int] = {
    ("django_oscar", "HIGH"): 52,
    ("django_oscar", "LOW"): 32,
    ("django_oscar", "MEDIUM"): 251,
    ("openfisca_france", "HIGH"): 36,
    ("openfisca_france", "LOW"): 29,
    ("openfisca_france", "MEDIUM"): 128,
    ("pretix", "HIGH"): 63,
    ("pretix", "LOW"): 15,
    ("pretix", "MEDIUM"): 124,
}


def _load_json(path: Path) -> JsonDict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[JsonDict]:
    records: list[JsonDict] = []

    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = line.strip()
        if not line:
            continue

        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"record {number} in {path} is not an object")
        records.append(value)

    return records


def _candidate_id(record: JsonDict) -> str:
    payload = "|".join(
        [
            str(record["source_id"]),
            str(record["file"]),
            str(record["enclosing_class"] or ""),
            str(record["function"]),
            str(record["line_start"]),
            str(record["line_end"]),
            str(record["function_sha256"]),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _registry_identity(rule: JsonDict) -> tuple[str, str, str, str]:
    return (
        str(rule["source_id"]),
        str(rule["external_source"]),
        str(rule["external_class"]),
        str(rule["external_method"]),
    )


def _candidate_identity(record: JsonDict) -> tuple[str, str, str, str]:
    return (
        str(record["source_id"]),
        str(record["file"]),
        str(record["enclosing_class"] or ""),
        str(record["function"]),
    )


def _evidence_bucket(record: JsonDict) -> str:
    has_test = bool(record["supporting_test_files"])
    has_doc = bool(record["supporting_doc_files"])

    if has_test and has_doc:
        return "TEST_AND_DOC"
    if has_test:
        return "TEST_ONLY"
    if has_doc:
        return "DOC_ONLY"
    return "NONE"


def _selection_hash(candidate_id: str) -> str:
    payload = f"{SELECTION_SEED}|{candidate_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _pool_digest(records: list[JsonDict]) -> str:
    ids = sorted(_candidate_id(record) for record in records)
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate candidate_id in eligible pool")
    return hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()


def _eligible_pool(
    records: list[JsonDict],
    registry: JsonDict,
) -> list[JsonDict]:
    raw_rules = registry.get("rules")
    if not isinstance(raw_rules, list):
        raise ValueError("registry rules must be a list")

    certified = {_registry_identity(rule) for rule in raw_rules if isinstance(rule, dict)}

    return [
        record
        for record in records
        if record.get("classification") == "ADAPTATION_REQUIRED"
        and record.get("business_relevance") == "STRONG"
        and _candidate_identity(record) not in certified
    ]


def _select_cohort(pool: list[JsonDict]) -> list[JsonDict]:
    groups: dict[tuple[str, str], list[JsonDict]] = defaultdict(list)

    for record in pool:
        key = (
            str(record["source_id"]),
            str(record["adaptation_complexity"]),
        )
        groups[key].append(record)

    actual_counts = {key: len(value) for key, value in groups.items()}
    if actual_counts != EXPECTED_STRATA:
        raise ValueError(f"strata changed: expected {EXPECTED_STRATA}, got {actual_counts}")

    selected: list[JsonDict] = []

    for source_id, complexity in sorted(EXPECTED_STRATA):
        population_size = EXPECTED_STRATA[(source_id, complexity)]
        group = groups[(source_id, complexity)]

        ranked = sorted(
            group,
            key=lambda record: (
                _selection_hash(_candidate_id(record)),
                _candidate_id(record),
            ),
        )

        for rank, record in enumerate(ranked[:PER_STRATUM], start=1):
            selected.append(
                {
                    "candidate_id": _candidate_id(record),
                    "selection_hash": _selection_hash(_candidate_id(record)),
                    "selection_rank_within_stratum": rank,
                    "stratum": {
                        "source_id": source_id,
                        "adaptation_complexity": complexity,
                        "population_size": population_size,
                        "sample_size": PER_STRATUM,
                        "design_weight_numerator": population_size,
                        "design_weight_denominator": PER_STRATUM,
                        "design_weight": population_size / PER_STRATUM,
                    },
                    "evidence_bucket": _evidence_bucket(record),
                    "candidate": record,
                }
            )

    if len(selected) != 90:
        raise ValueError(f"expected 90 selected candidates, got {len(selected)}")

    ids = [str(item["candidate_id"]) for item in selected]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate selected candidate_id")

    return selected


def _cohort_digest(selected: list[JsonDict]) -> str:
    payload = "\n".join(str(item["candidate_id"]) for item in selected)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def freeze_cohort(
    *,
    candidate_path: Path,
    registry_path: Path,
    output_dir: Path,
) -> JsonDict:
    actual_candidate_sha = hashlib.sha256(candidate_path.read_bytes()).hexdigest()

    if actual_candidate_sha != EXPECTED_CANDIDATE_SHA256:
        raise ValueError(f"candidate dataset hash changed: {actual_candidate_sha}")

    records = _load_jsonl(candidate_path)
    if len(records) != EXPECTED_CANDIDATE_COUNT:
        raise ValueError(f"expected {EXPECTED_CANDIDATE_COUNT} candidates, got {len(records)}")

    registry = _load_json(registry_path)
    pool = _eligible_pool(records, registry)

    if len(pool) != EXPECTED_POOL_SIZE:
        raise ValueError(f"expected eligible pool size {EXPECTED_POOL_SIZE}, got {len(pool)}")

    pool_digest = _pool_digest(pool)
    if pool_digest != EXPECTED_POOL_SHA256:
        raise ValueError(f"eligible pool digest changed: {pool_digest}")

    selected = _select_cohort(pool)
    cohort_digest = _cohort_digest(selected)

    source_counts = Counter(str(item["stratum"]["source_id"]) for item in selected)
    complexity_counts = Counter(str(item["stratum"]["adaptation_complexity"]) for item in selected)
    evidence_counts = Counter(str(item["evidence_bucket"]) for item in selected)

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "candidate_dataset_sha256": actual_candidate_sha,
        "eligible_pool_size": len(pool),
        "eligible_pool_sha256": pool_digest,
        "selection_seed": SELECTION_SEED,
        "allocation": "10_PER_SOURCE_X_COMPLEXITY_STRATUM",
        "sample_size": len(selected),
        "cohort_sha256": cohort_digest,
        "source_counts": dict(sorted(source_counts.items())),
        "complexity_counts": dict(sorted(complexity_counts.items())),
        "evidence_counts": dict(sorted(evidence_counts.items())),
        "strata": [
            {
                "source_id": source_id,
                "adaptation_complexity": complexity,
                "population_size": population_size,
                "sample_size": PER_STRATUM,
                "design_weight": population_size / PER_STRATUM,
            }
            for (source_id, complexity), population_size in sorted(EXPECTED_STRATA.items())
        ],
        "passed": True,
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    cohort_path = output_dir / "cohort.jsonl"
    cohort_path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in selected),
        encoding="utf-8",
    )

    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("benchmarks/v0.6/results/candidates.jsonl"),
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("benchmarks/v0.10/registry.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/results"),
    )
    args = parser.parse_args()

    summary = freeze_cohort(
        candidate_path=args.candidates,
        registry_path=args.registry,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 generalization cohort freeze")
    print(f"Eligible population: {summary['eligible_pool_size']}")
    print(f"Sample size: {summary['sample_size']}")
    print(f"Pool SHA256: {summary['eligible_pool_sha256']}")
    print(f"Cohort SHA256: {summary['cohort_sha256']}")
    print(f"Source counts: {summary['source_counts']}")
    print(f"Complexity counts: {summary['complexity_counts']}")
    print(f"Evidence counts: {summary['evidence_counts']}")
    print("PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
