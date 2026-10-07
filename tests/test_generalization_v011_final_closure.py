import json
from collections import Counter
from pathlib import Path

ROOT = Path("benchmarks/v0.11")

LEDGER = ROOT / "controlled_complex_closure" / "candidate_terminal_state.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_v011_final_terminal_distribution() -> None:
    rows = load_jsonl(LEDGER)

    assert len(rows) == 90

    assert all(row["state"] == "TERMINAL_ASSIGNED" for row in rows)

    dist = Counter(row["terminal_outcome"] for row in rows)

    assert dist == {
        "CERTIFIED_A1": 33,
        "CERTIFIED_A2": 17,
        "NOT_CERTIFIED_SEMANTIC_AMBIGUITY": 2,
        "NOT_CERTIFIED_UNSUPPORTED": 38,
    }


def test_final_nbptr_a2_evidence() -> None:
    root = ROOT / "final_a2_frontier" / "nbptr_a2"

    runtime = json.loads((root / "runtime_evidence.json").read_text(encoding="utf-8"))

    symbolic = json.loads((root / "symbolic_proof.json").read_text(encoding="utf-8"))

    certs = list(root.glob("CERT-V011-A2-*.json"))

    assert len(certs) == 1

    assert runtime["comparisons"] == 513
    assert runtime["adapter_mismatches"] == 0
    assert runtime["mutant_mismatches"] > 0
    assert runtime["passed"] is True

    assert symbolic["correct_solver_status"] == "unsat"
    assert symbolic["mutant_solver_status"] == "sat"
    assert symbolic["passed"] is True


def test_a1_dependency_closure() -> None:
    repair_root = ROOT / "final_a1_dependency_audit" / "repairs"

    summary = json.loads((repair_root / "repair_summary.json").read_text(encoding="utf-8"))

    proofs = load_jsonl(repair_root / "dependency_repair_proofs.jsonl")

    assert summary["terminalized"] == 90
    assert summary["pending"] == 0
    assert summary["scope_extension_performed"] is False

    assert len(proofs) == 3
    assert all(proof["passed"] is True for proof in proofs)

    assert all(proof["correct_solver_status"] == "unsat" for proof in proofs)

    assert all(proof["mutant_solver_status"] == "sat" for proof in proofs)


def test_a74d_is_superseded() -> None:
    rows = {row["candidate_id"]: row for row in load_jsonl(LEDGER)}

    row = rows["a74d4580a9effb73"]

    assert row["terminal_outcome"] == "NOT_CERTIFIED_UNSUPPORTED"

    assert row["reason_code"] == "NESTED_AND_OR_HELPERS_OUTSIDE_FROZEN_A1_CONTRACT_CLOSURE"

    for cid in (
        "4c7af63af2f89319",
        "61cf0e4af667580e",
        "fd4702ed1d79ff1f",
    ):
        assert rows[cid]["dependency_closure_status"] == "PROVED_RECURSIVE"
