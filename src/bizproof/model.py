from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Verdict(StrEnum):
    PROVED = "PROVED"
    DISPROVED = "DISPROVED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class InputSpec:
    name: str
    type_name: str
    minimum: int | None = None
    maximum: int | None = None
    label: str | None = None


@dataclass(frozen=True)
class TargetSpec:
    source: Path
    function: str


@dataclass(frozen=True)
class BusinessContract:
    contract_id: str
    title: str
    target: TargetSpec
    inputs: tuple[InputSpec, ...]
    precondition: str
    postcondition: str
    expected_outcome: str | None = None


@dataclass(frozen=True)
class Evidence:
    verdict: Verdict
    contract_id: str
    backend: str
    counterexample: dict[str, Any] | None = None
    observed_result: Any | None = None
    postcondition_satisfied: bool | None = None
    replay_validated: bool | None = None
    reason_code: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
