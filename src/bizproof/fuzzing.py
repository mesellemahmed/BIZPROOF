from __future__ import annotations

import json
import random
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from .contracts import load_contract
from .enum_backend import verify_by_enumeration
from .model import Verdict


@dataclass(frozen=True)
class GeneratedCase:
    case_id: str
    template: str
    variant: str
    source_path: Path
    contract_path: Path
    expected_verdict: Verdict


@dataclass(frozen=True)
class FuzzSummary:
    seed: int
    cases_requested: int
    cases_checked: int
    expected_proved: int
    expected_disproved: int
    oracle_label_mismatches: int
    verdict_disagreements: int
    false_proved: int
    false_disproved: int
    enum_unknowns: int
    z3_unknowns: int
    invalid_replays: int
    crashes: int
    runtime_seconds: float
    templates: dict[str, int]

    @property
    def passed(self) -> bool:
        return (
            self.cases_checked == self.cases_requested
            and self.oracle_label_mismatches == 0
            and self.verdict_disagreements == 0
            and self.false_proved == 0
            and self.false_disproved == 0
            and self.enum_unknowns == 0
            and self.z3_unknowns == 0
            and self.invalid_replays == 0
            and self.crashes == 0
        )


_COMPARATORS = ("<", "<=", ">", ">=", "==", "!=")
_MUTATED_COMPARATOR = {
    "<": "<=",
    "<=": "<",
    ">": ">=",
    ">=": ">",
    "==": "!=",
    "!=": "==",
}


def _write_case(
    root: Path,
    index: int,
    template: str,
    variant: str,
    source: str,
    inputs: dict[str, dict[str, Any]],
    postcondition: str,
) -> GeneratedCase:
    case_id = f"FD-{index:05d}"
    case_dir = root / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    source_path = case_dir / "target.py"
    contract_path = case_dir / "contract.yaml"
    source_path.write_text(source, encoding="utf-8")

    payload = {
        "id": case_id,
        "title": f"Differential fuzz case {index}",
        "target": {
            "source": str(source_path.relative_to(root.parent.parent.parent)),
            "function": "target",
        },
        "inputs": inputs,
        "precondition": "True",
        "postcondition": postcondition,
        "business": {
            "expected_outcome": "Generated semantic-equivalence contract.",
        },
    }
    contract_path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )

    return GeneratedCase(
        case_id=case_id,
        template=template,
        variant=variant,
        source_path=source_path,
        contract_path=contract_path,
        expected_verdict=Verdict.PROVED if variant == "correct" else Verdict.DISPROVED,
    )


def _threshold_case(root: Path, index: int, rng: random.Random, variant: str) -> GeneratedCase:
    op = rng.choice(_COMPARATORS)
    implementation_op = op if variant == "correct" else _MUTATED_COMPARATOR[op]
    threshold = rng.choice((-2, -1, 0, 1, 2))
    source = f"def target(x: int) -> bool:\n    return x {implementation_op} {threshold}\n"
    inputs: dict[str, dict[str, Any]] = {"x": {"type": "int", "min": -3, "max": 3, "label": "X"}}
    postcondition = f"result == (x {op} {threshold})"
    return _write_case(root, index, "threshold", variant, source, inputs, postcondition)


def _boolean_case(root: Path, index: int, rng: random.Random, variant: str) -> GeneratedCase:
    left_threshold = rng.choice((-1, 0, 1))
    right_threshold = rng.choice((-1, 0, 1))
    expected_join = rng.choice(("and", "or"))
    implementation_join = (
        expected_join if variant == "correct" else ("or" if expected_join == "and" else "and")
    )
    source = (
        "def target(x: int, y: int) -> bool:\n"
        f"    return (x >= {left_threshold}) {implementation_join} (y <= {right_threshold})\n"
    )
    inputs: dict[str, dict[str, Any]] = {
        "x": {"type": "int", "min": -3, "max": 3, "label": "X"},
        "y": {"type": "int", "min": -3, "max": 3, "label": "Y"},
    }
    postcondition = f"result == ((x >= {left_threshold}) {expected_join} (y <= {right_threshold}))"
    return _write_case(root, index, "boolean", variant, source, inputs, postcondition)


def _arithmetic_case(root: Path, index: int, rng: random.Random, variant: str) -> GeneratedCase:
    offset = rng.choice((1, 2, 3))
    implementation_offset = offset if variant == "correct" else -offset
    source = (
        "def target(x: int, y: int) -> bool:\n"
        f"    adjusted = x + ({implementation_offset})\n"
        "    return adjusted >= y\n"
    )
    inputs: dict[str, dict[str, Any]] = {
        "x": {"type": "int", "min": -3, "max": 3, "label": "X"},
        "y": {"type": "int", "min": -3, "max": 3, "label": "Y"},
    }
    postcondition = f"result == ((x + ({offset})) >= y)"
    return _write_case(root, index, "arithmetic", variant, source, inputs, postcondition)


def _branch_case(root: Path, index: int, rng: random.Random, variant: str) -> GeneratedCase:
    threshold = rng.choice((-1, 0, 1))
    implementation_threshold = threshold if variant == "correct" else threshold + 1
    source = (
        "def target(x: int, flag: bool) -> bool:\n"
        f"    if x >= {implementation_threshold}:\n"
        "        return flag\n"
        "    return not flag\n"
    )
    inputs: dict[str, dict[str, Any]] = {
        "x": {"type": "int", "min": -3, "max": 3, "label": "X"},
        "flag": {"type": "bool", "label": "Flag"},
    }
    postcondition = (
        f"result == (((x >= {threshold}) and flag) or ((not (x >= {threshold})) and (not flag)))"
    )
    return _write_case(root, index, "branch", variant, source, inputs, postcondition)


def _nested_case(root: Path, index: int, rng: random.Random, variant: str) -> GeneratedCase:
    outer = rng.choice((-1, 0, 1))
    inner = rng.choice((-1, 0, 1))
    implementation_inner = inner if variant == "correct" else inner + 1
    source = (
        "def target(x: int, y: int) -> bool:\n"
        "    shifted = x + 1\n"
        f"    if shifted > {outer}:\n"
        f"        if y < {implementation_inner}:\n"
        "            return True\n"
        "        return False\n"
        "    return y == 0\n"
    )
    inputs: dict[str, dict[str, Any]] = {
        "x": {"type": "int", "min": -3, "max": 3, "label": "X"},
        "y": {"type": "int", "min": -3, "max": 3, "label": "Y"},
    }
    postcondition = (
        "result == ((((x + 1) > "
        f"{outer}) and (y < {inner})) or "
        f"((not ((x + 1) > {outer})) and (y == 0)))"
    )
    return _write_case(root, index, "nested", variant, source, inputs, postcondition)


def _early_return_case(
    root: Path,
    index: int,
    rng: random.Random,
    variant: str,
) -> GeneratedCase:
    low = rng.choice((-2, -1, 0))
    high = rng.choice((0, 1, 2))
    implementation_high = high if variant == "correct" else high - 1
    source = (
        "def target(x: int, y: int) -> bool:\n"
        f"    if x < {low}:\n"
        "        return False\n"
        f"    if y > {implementation_high}:\n"
        "        return True\n"
        "    return x == y\n"
    )
    inputs: dict[str, dict[str, Any]] = {
        "x": {"type": "int", "min": -3, "max": 3, "label": "X"},
        "y": {"type": "int", "min": -3, "max": 3, "label": "Y"},
    }
    postcondition = (
        "result == (((not (x < "
        f"{low})) and (y > {high})) or "
        f"((not (x < {low})) and (not (y > {high})) and (x == y)))"
    )
    return _write_case(root, index, "early_return", variant, source, inputs, postcondition)


_GENERATORS = (
    _threshold_case,
    _boolean_case,
    _arithmetic_case,
    _branch_case,
    _nested_case,
    _early_return_case,
)


def generate_corpus(root: Path, *, cases: int, seed: int) -> list[GeneratedCase]:
    if cases < 1:
        raise ValueError("cases must be >= 1")

    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    generated: list[GeneratedCase] = []

    for index in range(1, cases + 1):
        generator = _GENERATORS[(index - 1) % len(_GENERATORS)]
        variant = "correct" if index % 2 else "mutant"
        generated.append(generator(root, index, rng, variant))

    manifest = {
        "seed": seed,
        "cases": cases,
        "templates": [case.template for case in generated],
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return generated


def run_fuzz_differential(
    root: Path,
    *,
    cases: int,
    seed: int,
    timeout_ms: int = 10_000,
) -> FuzzSummary:
    started = time.perf_counter()
    from .z3_backend import verify_with_z3

    generated = generate_corpus(root, cases=cases, seed=seed)

    expected_proved = 0
    expected_disproved = 0
    oracle_label_mismatches = 0
    verdict_disagreements = 0
    false_proved = 0
    false_disproved = 0
    enum_unknowns = 0
    z3_unknowns = 0
    invalid_replays = 0
    crashes = 0
    templates: dict[str, int] = {}

    for case in generated:
        templates[case.template] = templates.get(case.template, 0) + 1
        if case.expected_verdict is Verdict.PROVED:
            expected_proved += 1
        else:
            expected_disproved += 1

        try:
            contract = load_contract(case.contract_path)
            enum_evidence = verify_by_enumeration(contract)
            z3_evidence = verify_with_z3(contract, timeout_ms=timeout_ms)
        except Exception:
            crashes += 1
            continue

        if enum_evidence.verdict is Verdict.UNKNOWN:
            enum_unknowns += 1
        if z3_evidence.verdict is Verdict.UNKNOWN:
            z3_unknowns += 1

        if enum_evidence.verdict != case.expected_verdict:
            oracle_label_mismatches += 1

        if enum_evidence.verdict != z3_evidence.verdict:
            verdict_disagreements += 1
            if enum_evidence.verdict is Verdict.DISPROVED and z3_evidence.verdict is Verdict.PROVED:
                false_proved += 1
            if enum_evidence.verdict is Verdict.PROVED and z3_evidence.verdict is Verdict.DISPROVED:
                false_disproved += 1

        if z3_evidence.verdict is Verdict.DISPROVED and z3_evidence.replay_validated is not True:
            invalid_replays += 1

    return FuzzSummary(
        seed=seed,
        cases_requested=cases,
        cases_checked=len(generated),
        expected_proved=expected_proved,
        expected_disproved=expected_disproved,
        oracle_label_mismatches=oracle_label_mismatches,
        verdict_disagreements=verdict_disagreements,
        false_proved=false_proved,
        false_disproved=false_disproved,
        enum_unknowns=enum_unknowns,
        z3_unknowns=z3_unknowns,
        invalid_replays=invalid_replays,
        crashes=crashes,
        runtime_seconds=time.perf_counter() - started,
        templates=templates,
    )


def write_summary(summary: FuzzSummary, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(summary)
    payload["passed"] = summary.passed
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
