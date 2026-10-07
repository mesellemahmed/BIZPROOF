from pathlib import Path

from bizproof.contracts import load_contract
from bizproof.model import BusinessContract, Verdict
from bizproof.z3_backend import verify_with_z3

ROOT = Path(__file__).resolve().parents[1]


def _contract(name: str) -> BusinessContract:
    return load_contract(ROOT / "contracts" / name)


def test_z3_finds_replayed_counterexample() -> None:
    evidence = verify_with_z3(_contract("br_minor_account.yaml"))

    assert evidence.verdict is Verdict.DISPROVED
    assert evidence.counterexample is not None
    assert evidence.counterexample["age"] in {16, 17}
    assert evidence.counterexample["guardian_present"] is False
    assert evidence.observed_result is True
    assert evidence.postcondition_satisfied is False
    assert evidence.replay_validated is True


def test_z3_proves_correct_program() -> None:
    evidence = verify_with_z3(_contract("br_minor_account_correct.yaml"))
    assert evidence.verdict is Verdict.PROVED


def test_z3_proves_nested_supported_program() -> None:
    evidence = verify_with_z3(_contract("br_minor_account_nested.yaml"))
    assert evidence.verdict is Verdict.PROVED


def test_z3_returns_unknown_for_unsupported_loop() -> None:
    evidence = verify_with_z3(_contract("br_minor_account_unknown.yaml"))
    assert evidence.verdict is Verdict.UNKNOWN
    assert evidence.reason_code == "unsupported_or_invalid_semantics"
    assert evidence.reason is not None
    assert "For" in evidence.reason


def test_z3_returns_unknown_for_vacuous_precondition() -> None:
    evidence = verify_with_z3(_contract("br_minor_account_vacuous.yaml"))
    assert evidence.verdict is Verdict.UNKNOWN
    assert evidence.reason_code == "unsatisfiable_precondition"


def test_z3_rejects_decorated_function() -> None:
    evidence = verify_with_z3(_contract("br_minor_account_decorated.yaml"))
    assert evidence.verdict is Verdict.UNKNOWN
    assert evidence.reason is not None
    assert "decorated functions" in evidence.reason


def test_z3_rejects_floor_division() -> None:
    evidence = verify_with_z3(_contract("br_minor_account_division.yaml"))
    assert evidence.verdict is Verdict.UNKNOWN
    assert evidence.reason is not None
    assert "division and modulo" in evidence.reason


def test_z3_rejects_external_call() -> None:
    evidence = verify_with_z3(_contract("br_minor_account_call.yaml"))
    assert evidence.verdict is Verdict.UNKNOWN
    assert evidence.reason is not None
    assert "Call" in evidence.reason
