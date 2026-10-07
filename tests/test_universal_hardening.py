from __future__ import annotations

import ast
import hashlib
import importlib.util
import tempfile
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from bizproof.universal_closure import (
    certify_universal,
)

CASES = Path("benchmarks/v0.13/universal_closure/cases")


POSITIVE = (
    "structured_tuple.py",
    "structured_dict.py",
    "opaque_binding.py",
    "nested_logic.py",
    "state_effect.py",
    "mixed.py",
)


def _load_module(
    path: Path,
) -> ModuleType:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]

    name = "_bizproof_hardening_" + digest

    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")

    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    return module


def _rule(
    path: Path,
) -> Callable[..., Any]:
    module = _load_module(path)

    value = module.rule

    if not callable(value):
        raise TypeError("rule is not callable")

    return value


class _User:
    def __init__(
        self,
        *,
        is_staff: bool = False,
        code: int = 17,
    ) -> None:
        self.is_staff = is_staff
        self.code = code
        self.accepted = False
        self.saves = 0

    def save(
        self,
    ) -> None:
        self.saves += 1


class _Account:
    def __init__(
        self,
        balance: int,
    ) -> None:
        self.balance = balance
        self.saves = 0

    def save(
        self,
    ) -> None:
        self.saves += 1


def _runtime_oracle(
    name: str,
) -> bool:
    path = CASES / name
    rule = _rule(path)

    if name == "structured_tuple.py":
        for x in (
            -7,
            0,
            4,
            100,
        ):
            assert rule(x) == (
                x + 1,
                x > 0,
            )

        return True

    if name == "structured_dict.py":
        for x in (
            -3,
            0,
            9,
        ):
            assert rule(x) == {
                "original": x * 2,
                "adjusted": x + 1,
            }

        return True

    if name == "opaque_binding.py":
        for is_staff in (
            False,
            True,
        ):
            for enabled in (
                False,
                True,
            ):
                user = _User(is_staff=is_staff)

                assert rule(
                    user,
                    enabled,
                ) is (is_staff and enabled)

        return True

    if name == "nested_logic.py":
        samples = (
            (1, 2, 3),
            (1, 0, 3),
            (-1, 2, 3),
            (4, 5, 6),
        )

        for values in samples:
            assert rule(values) is all(value > 0 for value in values)

        return True

    if name == "state_effect.py":
        for balance, amount in (
            (10, 3),
            (0, 5),
            (7, -2),
        ):
            account = _Account(balance)

            result = rule(
                account,
                amount,
            )

            assert result == (balance + amount)

            assert account.balance == (balance + amount)

            assert account.saves == 1

        return True

    if name == "mixed.py":
        samples = (
            (1, 2, 3),
            (1, -1, 3),
            (0, 1, 2),
        )

        for values in samples:
            user = _User(code=29)

            expected = all(value > 0 for value in values)

            result = rule(
                user,
                values,
            )

            assert result == (
                expected,
                29,
            )

            assert user.accepted is expected

            assert user.saves == (1 if expected else 0)

        return True

    raise AssertionError(f"unknown development oracle: {name}")


MUTATIONS = {
    "structured_tuple.py": (
        "x + 1",
        "x - 1",
    ),
    "structured_dict.py": (
        '"adjusted": x + 1',
        '"adjusted": x - 1',
    ),
    "opaque_binding.py": (
        "user.is_staff and enabled",
        "user.is_staff or enabled",
    ),
    "nested_logic.py": (
        "value > 0",
        "value >= 0",
    ),
    "state_effect.py": (
        "account.balance + amount",
        "account.balance - amount",
    ),
    "mixed.py": (
        "accepted = all(",
        "accepted = any(",
    ),
}


def _observe_mutant_pair(
    name: str,
    original: Callable[..., Any],
    mutant: Callable[..., Any],
) -> bool:
    if name == "structured_tuple.py":
        return original(2) != mutant(2)

    if name == "structured_dict.py":
        return original(2) != mutant(2)

    if name == "opaque_binding.py":
        left = _User(is_staff=False)

        right = _User(is_staff=False)

        return original(
            left,
            True,
        ) != mutant(
            right,
            True,
        )

    if name == "nested_logic.py":
        witness = (
            1,
            0,
            1,
        )

        return original(witness) != mutant(witness)

    if name == "state_effect.py":
        left = _Account(10)
        right = _Account(10)

        original_result = original(
            left,
            3,
        )

        mutant_result = mutant(
            right,
            3,
        )

        return (
            original_result,
            left.balance,
            left.saves,
        ) != (
            mutant_result,
            right.balance,
            right.saves,
        )

    if name == "mixed.py":
        witness = (
            1,
            -1,
            1,
        )

        left = _User(code=31)
        right = _User(code=31)

        original_result = original(
            left,
            witness,
        )

        mutant_result = mutant(
            right,
            witness,
        )

        return (
            original_result,
            left.accepted,
            left.saves,
        ) != (
            mutant_result,
            right.accepted,
            right.saves,
        )

    raise AssertionError(f"unknown mutant case {name}")


def _mutant_detected(
    name: str,
    temp: Path,
) -> bool:
    source_path = CASES / name

    source = source_path.read_text(encoding="utf-8")

    old, new = MUTATIONS[name]

    count = source.count(old)

    if count != 1:
        raise AssertionError(f"{name}: expected one mutation site, found {count}")

    mutated = source.replace(
        old,
        new,
        1,
    )

    mutant_path = temp / ("mutant_" + name)

    mutant_path.write_text(
        mutated,
        encoding="utf-8",
    )

    original_rule = _rule(source_path)

    mutant_rule = _rule(mutant_path)

    return _observe_mutant_pair(
        name,
        original_rule,
        mutant_rule,
    )


def _metamorphic_variant(
    source: str,
) -> str:
    tree = ast.parse(source)

    return ast.unparse(tree) + "\n"


NEGATIVE_SOURCES = {
    "while_loop": """
def rule(x: int) -> int:
    while x > 0:
        x = x - 1
    return x
""",
    "for_loop": """
def rule(x: int) -> int:
    total = 0
    for value in range(x):
        total = total + value
    return total
""",
    "dynamic_call": """
def rule(x: int) -> int:
    return abs(x)
""",
}


@lru_cache(maxsize=1)
def build_hardening_summary() -> dict[str, Any]:
    deterministic = 0
    metamorphic = 0
    runtime_oracles = 0
    mutants = 0
    negative_rejections = 0

    outcome_profile: dict[
        str,
        str,
    ] = {}

    with tempfile.TemporaryDirectory(prefix="bizproof-v013-hardening-") as tmp_name:
        tmp = Path(tmp_name)

        for name in POSITIVE:
            source_path = CASES / name

            first = certify_universal(
                source_file=source_path,
                evidence_id=("hardening::" + name + "::a"),
            )

            second = certify_universal(
                source_file=source_path,
                evidence_id=("hardening::" + name + "::b"),
            )

            deterministic_keys = (
                "scientific_outcome",
                "certified",
                "a_level",
                "formal_obligation_count",
                "a2_obligation_count",
                "bindings",
                "state_bindings",
                "effects",
            )

            for key in deterministic_keys:
                assert first.get(key) == second.get(key), (
                    name,
                    key,
                    first.get(key),
                    second.get(key),
                )

            deterministic += 1

            outcome_profile[name] = str(first["scientific_outcome"])

            source = source_path.read_text(encoding="utf-8")

            variant_source = _metamorphic_variant(source)

            variant_path = tmp / ("variant_" + name)

            variant_path.write_text(
                variant_source,
                encoding="utf-8",
            )

            variant = certify_universal(
                source_file=variant_path,
                evidence_id=("hardening::" + name + "::metamorphic"),
            )

            assert variant["scientific_outcome"] == first["scientific_outcome"]

            assert variant.get("formal_obligation_count") == first.get("formal_obligation_count")

            assert variant.get("a2_obligation_count") == first.get("a2_obligation_count")

            metamorphic += 1

            assert _runtime_oracle(name)

            runtime_oracles += 1

            assert _mutant_detected(
                name,
                tmp,
            )

            mutants += 1

        for (
            name,
            source,
        ) in NEGATIVE_SOURCES.items():
            path = tmp / ("negative_" + name + ".py")

            path.write_text(
                source.strip() + "\n",
                encoding="utf-8",
            )

            result = certify_universal(
                source_file=path,
                evidence_id=("negative::" + name),
            )

            assert result["certified"] is False

            assert result["scientific_outcome"] == "UNSUPPORTED"

            negative_rejections += 1

    return {
        "schema_version": "BIZPROOF-V0.13-HARDENING-1",
        "positive_cases": len(POSITIVE),
        "deterministic_cases": deterministic,
        "metamorphic_preserved": metamorphic,
        "independent_runtime_oracles": runtime_oracles,
        "independent_mutants_detected": mutants,
        "negative_controls": len(NEGATIVE_SOURCES),
        "negative_controls_rejected": negative_rejections,
        "outcome_profile": outcome_profile,
        "engine_case_specific_routing": False,
        "development_oracles_case_specific": True,
        "development_oracles_used_by_engine": False,
        "external_holdout_cases_used": 0,
        "external_outcomes_observed": 0,
        "arbitrary_python_claim": False,
        "claim_scope": (
            "independent development-time hardening "
            "of the frozen generic certification pipeline; "
            "development oracles are not part of engine routing"
        ),
    }


def test_hardening_determinism() -> None:
    result = build_hardening_summary()

    assert result["deterministic_cases"] == 6


def test_hardening_metamorphic_preservation() -> None:
    result = build_hardening_summary()

    assert result["metamorphic_preserved"] == 6


def test_independent_runtime_oracle_and_mutants() -> None:
    result = build_hardening_summary()

    assert result["independent_runtime_oracles"] == 6

    assert result["independent_mutants_detected"] == 6


def test_negative_controls_rejected() -> None:
    result = build_hardening_summary()

    assert result["negative_controls_rejected"] == 3
