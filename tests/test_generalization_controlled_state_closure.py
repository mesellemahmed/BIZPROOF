from __future__ import annotations

from pathlib import Path

from bizproof.generalization_controlled_state_closure import (
    TARGETS,
    build,
)


def test_target_count() -> None:
    assert len(TARGETS) == 8


def test_controlled_state_batch(
    tmp_path: Path,
) -> None:
    summary = build(
        repo_root=Path(".").resolve(),
        output_dir=tmp_path,
    )

    assert summary["controlled_execution_established"] == 8

    assert summary["not_certified_execution"] == 0

    assert summary["not_certified_unsupported"] == 8

    assert summary["terminalized_after"] == 77

    assert summary["pending_after"] == 13
