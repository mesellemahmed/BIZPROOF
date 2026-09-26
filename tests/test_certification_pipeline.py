from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any


def _module() -> Any:
    return importlib.import_module("bizproof.certification_pipeline")


def test_canonical_digest_is_order_independent() -> None:
    module = _module()

    left = {
        "a": 1,
        "b": {
            "x": True,
            "y": "value",
        },
    }
    right = {
        "b": {
            "y": "value",
            "x": True,
        },
        "a": 1,
    }

    assert module._digest(left) == module._digest(right)


def test_digest_changes_when_evidence_changes() -> None:
    module = _module()

    original = {
        "status": "CERTIFIED",
        "proof": "PROVED",
    }
    modified = {
        "status": "CERTIFIED",
        "proof": "DISPROVED",
    }

    assert module._digest(original) != module._digest(modified)


def test_reviewer_report_mentions_certificate_digest(
    tmp_path: Path,
) -> None:
    module = _module()

    summary = {
        "claim_scope": "slice only",
        "certificates_configured": 1,
        "certificates_issued": 1,
        "certificates_failed": 0,
        "external_system_count": 1,
        "v08_total_comparisons": 2,
        "v08_correct_mismatches": 0,
        "v09_equivalences_proved": 1,
        "passed": True,
    }

    certificate = {
        "certificate_id": "CERT-X",
        "status": "CERTIFIED",
        "certification_scope": "RETURN_EXPRESSION",
        "provenance": {
            "source_id": "system",
            "resolved_commit": "a" * 40,
            "external_source": "rule.py",
        },
        "artifacts": {
            "adapter_path": "adapter.py",
            "contract_path": "contract.yaml",
        },
        "evidence": {
            "v0.7": {
                "correct_verdict": "PROVED",
            },
            "v0.8": {
                "comparisons": 2,
                "correct_mismatches": 0,
            },
            "v0.9": {
                "external_slice": "return business_rule",
                "correct_verdict": "PROVED",
                "solver_status": "unsat",
            },
        },
        "certificate_digest": "b" * 64,
        "failed_checks": [],
    }

    report = module._reviewer_report(
        summary,
        [certificate],
    )

    output = tmp_path / "report.md"
    output.write_text(report, encoding="utf-8")

    loaded = output.read_text(encoding="utf-8")
    assert "CERT-X" in loaded
    assert "CERTIFIED" in loaded
    assert "b" * 64 in loaded


def test_registry_has_four_distinct_certificates() -> None:
    registry = json.loads(Path("benchmarks/v0.10/registry.json").read_text(encoding="utf-8"))

    ids = [rule["certificate_id"] for rule in registry["rules"]]

    assert len(ids) == 4
    assert len(set(ids)) == 4
