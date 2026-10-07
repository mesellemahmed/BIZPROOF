from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import z3

from .generalization_structural_nationality_a1 import (
    CANDIDATE_ID,
    CLASS_NAME,
    EXPECTED_FUNCTION_SHA256,
    FUNCTION_NAME,
    SOURCE_RELATIVE,
)

FR = 0
CH = 1
OTHER = 2


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _locked_node(
    repo_root: Path,
) -> ast.FunctionDef:

    path = repo_root / SOURCE_RELATIVE
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    matches: list[ast.FunctionDef] = []

    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name == CLASS_NAME):
            continue

        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == FUNCTION_NAME:
                matches.append(item)

    if len(matches) != 1:
        raise ValueError("locked function not uniquely found")

    segment = (
        ast.get_source_segment(
            source,
            matches[0],
        )
        or ""
    )

    digest = _sha256(segment)

    if digest != EXPECTED_FUNCTION_SHA256:
        raise ValueError("locked function SHA mismatch")

    return matches[0]


class Translator:
    def __init__(self) -> None:

        self.nationality = z3.Int("nationality")

        self.eee = z3.Int("ressortissant_eee")

        self.duration = z3.Int("duration")

        self.eee_threshold = z3.Int("eee_threshold")

        self.non_eee_threshold = z3.Int("non_eee_threshold")

        self.env: dict[
            str,
            z3.ArithRef,
        ] = {}

    def _bool_int(
        self,
        condition: z3.BoolRef,
    ) -> z3.ArithRef:

        return z3.If(
            condition,
            z3.IntVal(1),
            z3.IntVal(0),
        )

    def expr(
        self,
        node: ast.expr,
    ) -> z3.ArithRef:

        if isinstance(node, ast.Name):
            if node.id not in self.env:
                raise ValueError("unknown name: " + node.id)
            return self.env[node.id]

        if isinstance(node, ast.Constant):
            if isinstance(
                node.value,
                bytes,
            ):
                if node.value == b"FR":
                    return z3.IntVal(FR)

                if node.value == b"CH":
                    return z3.IntVal(CH)

                return z3.IntVal(OTHER)

            if isinstance(
                node.value,
                bool,
            ):
                return z3.IntVal(int(node.value))

            if isinstance(
                node.value,
                int,
            ):
                return z3.IntVal(node.value)

            raise ValueError("unsupported constant: " + repr(node.value))

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "individu":
                if not node.args:
                    raise ValueError("individu lookup missing name")

                variable = node.args[0]

                if not (
                    isinstance(
                        variable,
                        ast.Constant,
                    )
                    and isinstance(
                        variable.value,
                        str,
                    )
                ):
                    raise ValueError("dynamic individu lookup")

                bindings = {
                    "nationalite": self.nationality,
                    "ressortissant_eee": self.eee,
                    "duree_possession_titre_sejour": self.duration,
                }

                try:
                    return bindings[variable.value]
                except KeyError as exc:
                    raise ValueError("unexpected individu binding: " + variable.value) from exc

            if isinstance(node.func, ast.Name) and node.func.id == "not_" and len(node.args) == 1:
                value = self.expr(node.args[0])

                return self._bool_int(value == 0)

            raise ValueError("unsupported call")

        if isinstance(node, ast.Attribute):
            if node.attr == "eee":
                return self.eee_threshold

            if node.attr == "non_eee":
                return self.non_eee_threshold

            raise ValueError("unsupported attribute: " + node.attr)

        if isinstance(node, ast.BinOp):
            left = self.expr(node.left)
            right = self.expr(node.right)

            if isinstance(node.op, ast.Add):
                return left + right

            if isinstance(node.op, ast.Mult):
                return left * right

            raise ValueError("unsupported binary operator")

        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise ValueError("chained comparison unsupported")

            left = self.expr(node.left)
            right = self.expr(node.comparators[0])

            op = node.ops[0]

            if isinstance(op, ast.Eq):
                return self._bool_int(left == right)

            if isinstance(op, ast.GtE):
                return self._bool_int(left >= right)

            raise ValueError("unsupported comparison")

        raise ValueError("unsupported AST node: " + type(node).__name__)

    def translate(
        self,
        function: ast.FunctionDef,
    ) -> z3.ArithRef:

        result: z3.ArithRef | None = None

        for statement in function.body:
            if isinstance(
                statement,
                ast.Assign,
            ):
                if len(statement.targets) != 1 or not isinstance(
                    statement.targets[0],
                    ast.Name,
                ):
                    raise ValueError("unsupported assignment")

                name = statement.targets[0].id

                if name == "duree_min_titre_sejour":
                    # Declarative parameter container.
                    # Only .eee and .non_eee are symbolic leaves.
                    continue

                self.env[name] = self.expr(statement.value)

                continue

            if isinstance(
                statement,
                ast.Return,
            ):
                if statement.value is None:
                    raise ValueError("empty return")

                result = self.expr(statement.value)

                continue

            raise ValueError("unsupported statement: " + type(statement).__name__)

        if result is None:
            raise ValueError("no return translated")

        return result


def independent_bsir(
    translator: Translator,
) -> z3.ArithRef:

    nationality = translator.nationality

    eee = translator.eee

    duration = translator.duration

    eee_threshold = translator.eee_threshold

    non_eee_threshold = translator.non_eee_threshold

    fr = z3.If(
        nationality == FR,
        1,
        0,
    )

    swiss = z3.If(
        nationality == CH,
        1,
        0,
    )

    eligible_eee = z3.If(
        (eee + swiss) * duration >= eee_threshold,
        1,
        0,
    )

    not_eee = z3.If(
        eee == 0,
        1,
        0,
    )

    eligible_non_eee = z3.If(
        not_eee * duration >= non_eee_threshold,
        1,
        0,
    )

    return fr + eligible_eee + eligible_non_eee


def mutant_bsir(
    translator: Translator,
) -> z3.ArithRef:

    nationality = translator.nationality

    eee = translator.eee

    duration = translator.duration

    fr = z3.If(
        nationality == FR,
        1,
        0,
    )

    eligible_eee = z3.If(
        eee * duration >= translator.eee_threshold,
        1,
        0,
    )

    not_eee = z3.If(
        eee == 0,
        1,
        0,
    )

    eligible_non_eee = z3.If(
        not_eee * duration >= translator.non_eee_threshold,
        1,
        0,
    )

    return fr + eligible_eee + eligible_non_eee


def run_proof(
    repo_root: Path,
) -> dict[str, Any]:

    function = _locked_node(repo_root)

    translator = Translator()

    source_expr = translator.translate(function)

    bsir_expr = independent_bsir(translator)

    mutant_expr = mutant_bsir(translator)

    domain = [
        z3.Or(
            translator.nationality == FR,
            translator.nationality == CH,
            translator.nationality == OTHER,
        ),
        z3.Or(
            translator.eee == 0,
            translator.eee == 1,
        ),
        translator.duration >= 0,
        translator.eee_threshold >= 0,
        translator.non_eee_threshold >= 0,
    ]

    correct_solver = z3.Solver()

    correct_solver.add(*domain)

    correct_solver.add(source_expr != bsir_expr)

    correct_status = correct_solver.check()

    mutant_solver = z3.Solver()

    mutant_solver.add(*domain)

    mutant_solver.add(source_expr != mutant_expr)

    mutant_status = mutant_solver.check()

    witness: (
        dict[
            str,
            int,
        ]
        | None
    ) = None

    if mutant_status == z3.sat:
        model = mutant_solver.model()

        symbols = {
            "nationality": translator.nationality,
            "ressortissant_eee": translator.eee,
            "duration": translator.duration,
            "eee_threshold": translator.eee_threshold,
            "non_eee_threshold": translator.non_eee_threshold,
        }

        witness = {}

        for name, symbol in symbols.items():
            value = model.eval(
                symbol,
                model_completion=True,
            )

            witness[name] = value.as_long()

    result: dict[
        str,
        Any,
    ] = {
        "candidate_id": CANDIDATE_ID,
        "function_sha256": EXPECTED_FUNCTION_SHA256,
        "authoring_mode": "DECLARATIVE_SOURCE_TO_BVC",
        "bytes_frontend": ("FR/CH/OTHER opaque equivalence classes"),
        "semantic_binding_scope": [
            ("individu('nationalite', period)"),
            ("individu('ressortissant_eee', period)"),
            ("individu('duree_possession_titre_sejour', period)"),
            ("duree_min_titre_sejour.eee"),
            ("duree_min_titre_sejour.non_eee"),
        ],
        "symbolic_domain": (
            "nationality partition "
            "{FR,CH,OTHER}; "
            "EEE in {0,1}; "
            "unbounded nonnegative duration "
            "and thresholds"
        ),
        "correct_solver_status": str(correct_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_solver_status": str(mutant_status),
        "mutant_disproved": mutant_status == z3.sat,
        "mutant_counterexample": witness,
        "certification_claim": False,
    }

    result["passed"] = result["correct_proved"] and result["mutant_disproved"]

    canonical = json.dumps(
        result,
        sort_keys=True,
        separators=(",", ":"),
    )

    result["proof_digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return result


def main() -> int:

    result = run_proof(Path(".").resolve())

    out = Path("benchmarks/v0.11/structural_nationality_a1")

    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    (out / "symbolic_proof.json").write_text(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "candidate       :",
        result["candidate_id"],
    )

    print(
        "correct solver  :",
        result["correct_solver_status"],
    )

    print(
        "correct proved  :",
        result["correct_proved"],
    )

    print(
        "mutant solver   :",
        result["mutant_solver_status"],
    )

    print(
        "mutant disproved:",
        result["mutant_disproved"],
    )

    print(
        "counterexample  :",
        result["mutant_counterexample"],
    )

    print(
        "W9-B2 Z3 GATE   :",
        ("PASS" if result["passed"] else "FAIL"),
    )

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
