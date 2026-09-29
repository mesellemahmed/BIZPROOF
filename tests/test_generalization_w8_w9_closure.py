import json
from pathlib import Path

from bizproof.generalization_controlled_complex_closure import TARGETS
from bizproof.generalization_controlled_complex_terminal import (
    A2_FOLLOWUP,
    CLOSE_UNSUPPORTED,
    _validate_partition,
)
from bizproof.generalization_structural_nationality_a1 import run
from bizproof.generalization_structural_nationality_symbolic import run_proof

CID = "d28505f251600d52"


def test_w8_partition_is_exact() -> None:
    _validate_partition()

    assert len(TARGETS) == 9
    assert len(CLOSE_UNSUPPORTED) == 7
    assert len(A2_FOLLOWUP) == 2
    assert not (CLOSE_UNSUPPORTED & A2_FOLLOWUP)
    assert set(TARGETS) == CLOSE_UNSUPPORTED | A2_FOLLOWUP


def test_w9_nationality_runtime_evidence() -> None:
    result = run(Path(".").resolve())

    assert result["candidate_id"] == CID
    assert result["comparisons"] == 378
    assert result["mutant_mismatches"] == 39
    assert result["source_execution_established"] is True
    assert result["mutant_sensitive"] is True
    assert result["passed"] is True
    assert result["certification_claim"] is False


def test_w9_nationality_symbolic_proof() -> None:
    result = run_proof(Path(".").resolve())

    assert result["candidate_id"] == CID
    assert result["correct_solver_status"] == "unsat"
    assert result["correct_proved"] is True
    assert result["mutant_solver_status"] == "sat"
    assert result["mutant_disproved"] is True
    assert result["passed"] is True
    assert result["certification_claim"] is False


def test_w9_ledger_is_86_of_90() -> None:
    path = Path("benchmarks/v0.11/controlled_complex_closure/candidate_terminal_state.jsonl")

    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]

    terminal = [x for x in rows if x["state"] == "TERMINAL_ASSIGNED"]
    pending = [x for x in rows if x["state"] == "PENDING_UNASSIGNED"]

    assert len(rows) == 90
    assert len(terminal) == 86
    assert len(pending) == 4

    row = next(x for x in rows if x["candidate_id"] == CID)

    assert row["terminal_outcome"] == "CERTIFIED_A1"
    assert row["certificate_id"].startswith("CERT-V011-A1-")
