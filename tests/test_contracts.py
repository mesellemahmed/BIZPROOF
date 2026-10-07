from pathlib import Path

from bizproof.contracts import load_contract

ROOT = Path(__file__).resolve().parents[1]


def test_contract_loads() -> None:
    contract = load_contract(ROOT / "contracts" / "br_minor_account.yaml")
    assert contract.contract_id == "BR-001"
    assert contract.target.function == "can_open_account"
    assert [spec.name for spec in contract.inputs] == ["age", "guardian_present"]
