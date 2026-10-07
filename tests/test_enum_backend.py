from pathlib import Path

from bizproof.contracts import load_contract
from bizproof.enum_backend import verify_by_enumeration
from bizproof.model import Verdict

ROOT = Path(__file__).resolve().parents[1]


def test_enum_finds_counterexample() -> None:
    contract = load_contract(ROOT / "contracts" / "br_minor_account.yaml")
    evidence = verify_by_enumeration(contract)

    assert evidence.verdict is Verdict.DISPROVED
    assert evidence.counterexample is not None
    assert evidence.counterexample["age"] in {16, 17}
    assert evidence.counterexample["guardian_present"] is False
    assert evidence.observed_result is True
    assert evidence.postcondition_satisfied is False
    assert evidence.replay_validated is True


def test_enum_proves_correct_bounded_program() -> None:
    contract = load_contract(ROOT / "contracts" / "br_minor_account_correct.yaml")
    evidence = verify_by_enumeration(contract)
    assert evidence.verdict is Verdict.PROVED


def test_enum_returns_unknown_for_vacuous_precondition() -> None:
    contract = load_contract(ROOT / "contracts" / "br_minor_account_vacuous.yaml")
    evidence = verify_by_enumeration(contract)
    assert evidence.verdict is Verdict.UNKNOWN
    assert evidence.reason_code == "unsatisfiable_precondition"
