from __future__ import annotations

import hashlib
from pathlib import Path

from bizproof.certification_pipeline import (
    MISSING_FILE_SHA256,
    _reviewer_report,
    _sha256_file,
    _sha256_or_missing,
)


def test_sha256_or_missing_matches_existing_file(
    tmp_path: Path,
) -> None:

    artifact = tmp_path / "artifact.txt"

    artifact.write_text(
        "BIZPROOF",
        encoding="utf-8",
    )

    expected = hashlib.sha256(artifact.read_bytes()).hexdigest()

    assert _sha256_file(artifact) == expected

    assert _sha256_or_missing(artifact) == expected


def test_sha256_or_missing_does_not_throw_for_missing_file(
    tmp_path: Path,
) -> None:

    missing = tmp_path / "does-not-exist.py"

    assert not missing.exists()

    assert _sha256_or_missing(missing) == MISSING_FILE_SHA256


def test_reviewer_report_accepts_reduced_failed_certificate() -> None:

    report = _reviewer_report(
        {},
        [
            {
                "certificate_id": "NEGATIVE",
                "status": "FAILED",
                "failed_checks": [
                    "external-source-exists",
                ],
            }
        ],
    )

    assert "### NEGATIVE" in report

    assert "Status: **FAILED**" in report

    assert "MISSING" in report

    assert "external-source-exists" in report


def test_reviewer_report_accepts_empty_inputs() -> None:

    report = _reviewer_report(
        {},
        [],
    )

    assert "Pipeline result: FAIL" in report

    assert "MISSING" in report
