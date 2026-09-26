from __future__ import annotations

import importlib
from typing import Any


def _module() -> Any:
    return importlib.import_module("bizproof.generalization_cohort")


def _record(source: str, complexity: str, index: int) -> dict[str, Any]:
    return {
        "adaptation_complexity": complexity,
        "business_relevance": "STRONG",
        "classification": "ADAPTATION_REQUIRED",
        "file": f"{source}/rule_{complexity}_{index}.py",
        "function": f"rule_{index}",
        "function_sha256": f"{index:064x}"[-64:],
        "source_file_sha256": "a" * 64,
        "source_id": source,
        "supporting_doc_files": [],
        "supporting_test_files": [],
        "enclosing_class": "Rule",
        "line_start": index + 1,
        "line_end": index + 2,
    }


def test_candidate_id_is_stable() -> None:
    module = _module()
    record = _record("django_oscar", "LOW", 1)

    assert module._candidate_id(record) == module._candidate_id(dict(record))


def test_selection_hash_is_stable() -> None:
    module = _module()

    value = module._selection_hash("abc")
    assert len(value) == 64
    assert value == module._selection_hash("abc")


def test_evidence_buckets() -> None:
    module = _module()

    record = _record("pretix", "LOW", 1)
    assert module._evidence_bucket(record) == "NONE"

    record["supporting_test_files"] = ["test.py"]
    assert module._evidence_bucket(record) == "TEST_ONLY"

    record["supporting_doc_files"] = ["doc.rst"]
    assert module._evidence_bucket(record) == "TEST_AND_DOC"

    record["supporting_test_files"] = []
    assert module._evidence_bucket(record) == "DOC_ONLY"


def test_balanced_selection_uses_ten_per_real_stratum() -> None:
    module = _module()

    pool = []
    counter = 1

    for (source, complexity), population_size in module.EXPECTED_STRATA.items():
        for _ in range(population_size):
            pool.append(_record(source, complexity, counter))
            counter += 1

    selected = module._select_cohort(pool)

    assert len(selected) == 90
    assert len({item["candidate_id"] for item in selected}) == 90

    counts: dict[tuple[str, str], int] = {}
    for item in selected:
        key = (
            item["stratum"]["source_id"],
            item["stratum"]["adaptation_complexity"],
        )
        counts[key] = counts.get(key, 0) + 1

    assert set(counts) == set(module.EXPECTED_STRATA)
    assert set(counts.values()) == {10}
