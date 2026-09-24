from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .contracts import load_contract
from .enum_backend import verify_by_enumeration
from .model import Verdict
from .z3_backend import verify_with_z3


@dataclass(frozen=True)
class DifferentialSummary:
    contracts_checked: int
    verdict_disagreements: int
    invalid_replays: int
    unexpected_unknowns: int

    @property
    def passed(self) -> bool:
        return (
            self.verdict_disagreements == 0
            and self.invalid_replays == 0
            and self.unexpected_unknowns == 0
        )


def run_differential_suite(directory: Path) -> DifferentialSummary:
    contract_paths = sorted(directory.glob("*.yaml"))
    disagreements = 0
    invalid_replays = 0
    unexpected_unknowns = 0

    for contract_path in contract_paths:
        contract = load_contract(contract_path)
        enum_evidence = verify_by_enumeration(contract)
        z3_evidence = verify_with_z3(contract)

        if enum_evidence.verdict != z3_evidence.verdict:
            disagreements += 1

        if z3_evidence.verdict is Verdict.DISPROVED and z3_evidence.replay_validated is not True:
            invalid_replays += 1

        if z3_evidence.verdict is Verdict.UNKNOWN:
            unexpected_unknowns += 1

    return DifferentialSummary(
        contracts_checked=len(contract_paths),
        verdict_disagreements=disagreements,
        invalid_replays=invalid_replays,
        unexpected_unknowns=unexpected_unknowns,
    )
