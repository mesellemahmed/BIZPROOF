from __future__ import annotations

import ast
import hashlib
import itertools
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

CANDIDATE_ID = "d28505f251600d52"

EXPECTED_FUNCTION_SHA256 = "4c0cdd7d5ced36267b9310d42ea5857ace57478505d2a89fec9234435da1474e"

SOURCE_RELATIVE = (
    "external_sources/v0.6/openfisca_france/"
    "openfisca_france/model/prestations/minima_sociaux/rsa.py"
)

CLASS_NAME = "rsa_condition_nationalite"
FUNCTION_NAME = "formula_2009_06_01"


def _sha256(
    value: str,
) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _extract_locked_function(
    repo_root: Path,
) -> tuple[Callable[..., Any], str]:

    path = repo_root / SOURCE_RELATIVE

    source = path.read_text(encoding="utf-8")

    tree = ast.parse(
        source,
        filename=str(path),
    )

    matches: list[ast.FunctionDef] = []

    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name == CLASS_NAME):
            continue

        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == FUNCTION_NAME:
                matches.append(item)

    if len(matches) != 1:
        raise ValueError("locked function not uniquely found")

    function_node = matches[0]

    segment = (
        ast.get_source_segment(
            source,
            function_node,
        )
        or ""
    )

    digest = _sha256(segment)

    if digest != EXPECTED_FUNCTION_SHA256:
        raise ValueError(f"locked function SHA mismatch: {digest}")

    module = ast.Module(
        body=[
            function_node,
        ],
        type_ignores=[],
    )

    ast.fix_missing_locations(module)

    namespace: dict[str, Any] = {
        "not_": lambda value: not value,
    }

    exec(
        compile(
            module,
            str(path),
            "exec",
        ),
        namespace,
    )

    function = namespace[FUNCTION_NAME]

    if not callable(function):
        raise TypeError("extracted source is not callable")

    return (
        cast(
            Callable[..., Any],
            function,
        ),
        digest,
    )


class Individu:
    def __init__(
        self,
        *,
        nationalite: bytes,
        ressortissant_eee: int,
        duree: int,
    ) -> None:

        self.values = {
            "nationalite": nationalite,
            "ressortissant_eee": ressortissant_eee,
            "duree_possession_titre_sejour": duree,
        }

    def __call__(
        self,
        name: str,
        period: Any,
    ) -> Any:

        del period

        return self.values[name]


def _parameters(
    eee_threshold: int,
    non_eee_threshold: int,
) -> Callable[[Any], Any]:

    root = SimpleNamespace(
        prestations_sociales=SimpleNamespace(
            solidarite_insertion=SimpleNamespace(
                minima_sociaux=SimpleNamespace(
                    rsa=SimpleNamespace(
                        rsa_cond=SimpleNamespace(
                            duree_min_titre_sejour=SimpleNamespace(
                                eee=eee_threshold,
                                non_eee=non_eee_threshold,
                            )
                        )
                    )
                )
            )
        )
    )

    def parameters(
        period: Any,
    ) -> Any:

        del period
        return root

    return parameters


def _mutant(
    *,
    nationalite: bytes,
    ressortissant_eee: int,
    duree: int,
    eee_threshold: int,
    non_eee_threshold: int,
) -> int:

    fr = nationalite == b"FR"

    # Intentional mutant:
    # Swiss nationality omitted from EEE path.
    eligibilite_eee = ressortissant_eee * duree >= eee_threshold

    eligibilite_non_eee = (not ressortissant_eee) * duree >= non_eee_threshold

    return int(fr + eligibilite_eee + eligibilite_non_eee)


def run(
    repo_root: Path,
) -> dict[str, Any]:

    function, digest = _extract_locked_function(repo_root)

    nationalities = [
        b"FR",
        b"CH",
        b"DE",
    ]

    eee_values = [
        0,
        1,
    ]

    durations = [
        0,
        1,
        2,
        4,
        5,
        6,
        10,
    ]

    thresholds = [
        1,
        5,
        10,
    ]

    comparisons = 0
    mutant_mismatches = 0

    examples: list[dict[str, Any]] = []

    for (
        nationality,
        eee,
        duration,
        eee_threshold,
        non_eee_threshold,
    ) in itertools.product(
        nationalities,
        eee_values,
        durations,
        thresholds,
        thresholds,
    ):
        external = function(
            Individu(
                nationalite=nationality,
                ressortissant_eee=eee,
                duree=duration,
            ),
            "PERIOD",
            _parameters(
                eee_threshold,
                non_eee_threshold,
            ),
        )

        mutant = _mutant(
            nationalite=nationality,
            ressortissant_eee=eee,
            duree=duration,
            eee_threshold=eee_threshold,
            non_eee_threshold=non_eee_threshold,
        )

        comparisons += 1

        if external != mutant:
            mutant_mismatches += 1

            if len(examples) < 5:
                examples.append(
                    {
                        "nationality": nationality.decode(),
                        "eee": eee,
                        "duration": duration,
                        "eee_threshold": eee_threshold,
                        "non_eee_threshold": non_eee_threshold,
                        "external": int(external),
                        "mutant": int(mutant),
                    }
                )

    result = {
        "candidate_id": CANDIDATE_ID,
        "function_sha256": digest,
        "runtime_domain": (
            "nationality in {FR,CH,OTHER}; "
            "EEE in {0,1}; "
            "duration in {0,1,2,4,5,6,10}; "
            "EEE/non-EEE thresholds in {1,5,10}"
        ),
        "comparisons": comparisons,
        "mutant_mismatches": mutant_mismatches,
        "mutant_examples": examples,
        "source_execution_established": comparisons == 378,
        "mutant_sensitive": mutant_mismatches > 0,
        "certification_claim": False,
    }

    result["passed"] = result["source_execution_established"] and result["mutant_sensitive"]

    return result


def main() -> int:

    result = run(Path(".").resolve())

    out = Path("benchmarks/v0.11/structural_nationality_a1")

    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    (out / "runtime_evidence.json").write_text(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "candidate          :",
        result["candidate_id"],
    )

    print(
        "function SHA       :",
        result["function_sha256"],
    )

    print(
        "runtime comparisons:",
        result["comparisons"],
    )

    print(
        "mutant mismatches  :",
        result["mutant_mismatches"],
    )

    print(
        "source execution   :",
        result["source_execution_established"],
    )

    print(
        "mutant sensitive   :",
        result["mutant_sensitive"],
    )

    print(
        "W9-B1 RUNTIME GATE :",
        ("PASS" if result["passed"] else "FAIL"),
    )

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
