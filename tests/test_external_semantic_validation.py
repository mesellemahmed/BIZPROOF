from __future__ import annotations

import json
from pathlib import Path

from bizproof.contracts import load_contract
from bizproof.model import Verdict
from bizproof.z3_backend import verify_with_z3


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_v07_catalog_shape() -> None:
    root = _repo_root()
    catalog = json.loads((root / "benchmarks/v0.7/catalog.json").read_text(encoding="utf-8"))

    rules = catalog["rules"]
    assert len(rules) == 4
    assert {rule["source_id"] for rule in rules} == {
        "openfisca_france",
        "django_oscar",
    }

    for rule in rules:
        assert rule["source_anchors"]
        assert rule["evidence_anchors"]
        assert rule["adapter_operations"]
        assert rule["expected_correct_verdict"] == "PROVED"
        assert rule["expected_mutant_verdict"] == "DISPROVED"


def test_v07_correct_adapters_are_proved() -> None:
    root = _repo_root()
    catalog = json.loads((root / "benchmarks/v0.7/catalog.json").read_text(encoding="utf-8"))

    for rule in catalog["rules"]:
        contract = load_contract(root / rule["correct_contract"])
        evidence = verify_with_z3(contract)
        assert evidence.verdict == Verdict.PROVED


def test_v07_mutants_are_disproved_with_replay() -> None:
    root = _repo_root()
    catalog = json.loads((root / "benchmarks/v0.7/catalog.json").read_text(encoding="utf-8"))

    for rule in catalog["rules"]:
        contract = load_contract(root / rule["mutant_contract"])
        evidence = verify_with_z3(contract)
        assert evidence.verdict == Verdict.DISPROVED
        assert evidence.replay_validated is True
        assert evidence.counterexample is not None
