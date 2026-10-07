from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any

import z3

ROOT = Path("benchmarks/v0.11")

DECISIONS = ROOT / "final_a1_dependency_audit" / "dependency_gap_decisions.jsonl"

LEDGER = ROOT / "controlled_complex_closure" / "candidate_terminal_state.jsonl"

OUT = ROOT / "final_a1_dependency_audit" / "repairs"

OUT.mkdir(
    parents=True,
    exist_ok=True,
)


WHERE_MIN_IDS = {
    "4c7af63af2f89319",
    "fd4702ed1d79ff1f",
}

NOT_ID = "61cf0e4af667580e"

RETRACT_ID = "a74d4580a9effb73"

REPAIRED_IDS = WHERE_MIN_IDS | {NOT_ID}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def registry_matches(
    value: Any,
    primitive: str,
) -> list[dict[str, Any]]:

    result: list[dict[str, Any]] = []

    if isinstance(value, dict):
        if value.get("primitive") == primitive:
            result.append(value)

        for child in value.values():
            result.extend(
                registry_matches(
                    child,
                    primitive,
                )
            )

    elif isinstance(value, list):
        for child in value:
            result.extend(
                registry_matches(
                    child,
                    primitive,
                )
            )

    return result


def compact_registry_record(
    value: dict[str, Any],
) -> dict[str, Any]:

    keys = (
        "primitive",
        "contract_id",
        "semantic_contract",
        "semantic_contract_id",
        "contract",
        "status",
        "definition_status",
        "binding_id",
    )

    return {key: value[key] for key in keys if key in value}


binding_registry = json.loads(
    (ROOT / "contracts" / "binding_registry.json").read_text(encoding="utf-8")
)

semantic_registry = json.loads(
    (ROOT / "semantic_evidence" / "semantic_registry.json").read_text(encoding="utf-8")
)


registry_evidence: dict[str, dict[str, Any]] = {}

for primitive in (
    "where",
    "min_",
    "not_",
    "and_",
    "or_",
):
    matches = registry_matches(
        binding_registry,
        primitive,
    ) + registry_matches(
        semantic_registry,
        primitive,
    )

    registry_evidence[primitive] = {
        "match_count": len(matches),
        "records": [compact_registry_record(item) for item in matches[:10]],
    }


assert registry_evidence["where"]["match_count"] > 0

assert registry_evidence["min_"]["match_count"] > 0

assert registry_evidence["not_"]["match_count"] > 0


decision_rows = {row["candidate_id"]: row for row in load_jsonl(DECISIONS)}


def longest_expression(
    cid: str,
) -> str:

    raw = decision_rows[cid].get("unique_nested_expressions")

    if not isinstance(
        raw,
        list,
    ):
        raise TypeError("unique_nested_expressions must be a list")

    expressions: list[str] = []

    for value in raw:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError("nested expression must be a string")

        expressions.append(value)

    if not expressions:
        raise ValueError("no nested expressions for " + cid)

    return max(
        expressions,
        key=len,
    )


def attr_path(
    node: ast.Attribute,
) -> str:

    parts = [node.attr]

    value: ast.expr = node.value

    while isinstance(
        value,
        ast.Attribute,
    ):
        parts.append(value.attr)

        value = value.value

    if not isinstance(
        value,
        ast.Name,
    ):
        raise ValueError("unsupported attribute root")

    parts.append(value.id)

    return ".".join(reversed(parts))


class WhereMinTranslator:
    def __init__(self) -> None:

        self.bool_vars = {
            "invalide": z3.Bool("invalide"),
            "annee1": z3.Bool("annee1"),
        }

        names = (
            "P.plafond_invalides",
            "P.plafond_maximum_1ere_annee",
            "P.plafond_1ere_annee",
            "P.increment_plafond",
            "nb_pac_majoration_plafond",
            "f7dl",
            "P.plafond_maximum",
            "P.plafond",
        )

        self.real_vars = {
            name: z3.Real(
                name.replace(
                    ".",
                    "_",
                )
            )
            for name in names
        }

    @staticmethod
    def as_bool(
        value: Any,
    ) -> Any:

        if z3.is_bool(value):
            return value

        return value != 0

    def expr(
        self,
        node: ast.expr,
    ) -> Any:

        if isinstance(
            node,
            ast.Name,
        ):
            if node.id in (self.bool_vars):
                return self.bool_vars[node.id]

            if node.id in (self.real_vars):
                return self.real_vars[node.id]

            raise ValueError("unknown name: " + node.id)

        if isinstance(
            node,
            ast.Attribute,
        ):
            path = attr_path(node)

            return self.real_vars[path]

        if isinstance(
            node,
            ast.Constant,
        ):
            if isinstance(
                node.value,
                (int, float),
            ):
                return z3.RealVal(str(node.value))

            raise ValueError("unsupported constant")

        if isinstance(
            node,
            ast.BinOp,
        ):
            left = self.expr(node.left)

            right = self.expr(node.right)

            if isinstance(
                node.op,
                ast.Add,
            ):
                return left + right

            if isinstance(
                node.op,
                ast.Sub,
            ):
                return left - right

            if isinstance(
                node.op,
                ast.Mult,
            ):
                return left * right

            raise ValueError("unsupported binop")

        if isinstance(
            node,
            ast.Call,
        ):
            if not isinstance(
                node.func,
                ast.Name,
            ):
                raise ValueError("unsupported call")

            name = node.func.id

            if name == "where":
                cond = self.expr(node.args[0])

                yes = self.expr(node.args[1])

                no = self.expr(node.args[2])

                return z3.If(
                    self.as_bool(cond),
                    yes,
                    no,
                )

            if name == "min_":
                left = self.expr(node.args[0])

                right = self.expr(node.args[1])

                return z3.If(
                    left <= right,
                    left,
                    right,
                )

            raise ValueError("unsupported helper: " + name)

        raise ValueError("unsupported AST: " + type(node).__name__)


def where_min_target(
    t: WhereMinTranslator,
) -> Any:

    b = t.bool_vars
    r = t.real_vars

    first_a = r["P.plafond_maximum_1ere_annee"]

    first_b = r["P.plafond_1ere_annee"] + r["P.increment_plafond"] * (
        r["nb_pac_majoration_plafond"] + r["f7dl"]
    )

    later_a = r["P.plafond_maximum"]

    later_b = r["P.plafond"] + r["P.increment_plafond"] * (
        r["nb_pac_majoration_plafond"] + r["f7dl"]
    )

    first_min = z3.If(
        first_a <= first_b,
        first_a,
        first_b,
    )

    later_min = z3.If(
        later_a <= later_b,
        later_a,
        later_b,
    )

    inner = z3.If(
        b["annee1"],
        first_min,
        later_min,
    )

    return z3.If(
        b["invalide"],
        r["P.plafond_invalides"],
        inner,
    )


def where_min_mutant(
    t: WhereMinTranslator,
) -> Any:

    b = t.bool_vars
    r = t.real_vars

    first_a = r["P.plafond_maximum_1ere_annee"]

    first_b = r["P.plafond_1ere_annee"] + r["P.increment_plafond"] * (
        r["nb_pac_majoration_plafond"] + r["f7dl"]
    )

    # Intentional mutation:
    # max instead of min.
    first_mutant = z3.If(
        first_a >= first_b,
        first_a,
        first_b,
    )

    later_a = r["P.plafond_maximum"]

    later_b = r["P.plafond"] + r["P.increment_plafond"] * (
        r["nb_pac_majoration_plafond"] + r["f7dl"]
    )

    later_min = z3.If(
        later_a <= later_b,
        later_a,
        later_b,
    )

    inner = z3.If(
        b["annee1"],
        first_mutant,
        later_min,
    )

    return z3.If(
        b["invalide"],
        r["P.plafond_invalides"],
        inner,
    )


def prove_where_min(
    cid: str,
) -> dict[str, Any]:

    expression = longest_expression(cid)

    tree = ast.parse(
        expression,
        mode="eval",
    )

    translator = WhereMinTranslator()

    source_expr = translator.expr(tree.body)

    target_expr = where_min_target(translator)

    mutant_expr = where_min_mutant(translator)

    correct = z3.Solver()

    correct.add(source_expr != target_expr)

    correct_status = correct.check()

    mutant = z3.Solver()

    mutant.add(source_expr != mutant_expr)

    mutant_status = mutant.check()

    return {
        "candidate_id": cid,
        "repair_kind": "RECURSIVE_WHERE_MIN_CLOSURE",
        "source_expression": expression,
        "required_contracts": [
            "where",
            "min_",
        ],
        "registry_evidence": {
            "where": registry_evidence["where"],
            "min_": registry_evidence["min_"],
        },
        "correct_solver_status": str(correct_status),
        "mutant_solver_status": str(mutant_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_disproved": mutant_status == z3.sat,
        "passed": (correct_status == z3.unsat and mutant_status == z3.sat),
    }


def prove_not_leaf() -> dict[str, Any]:

    expression = longest_expression(NOT_ID)

    tree = ast.parse(
        expression,
        mode="eval",
    )

    root = tree.body

    if not (
        isinstance(
            root,
            ast.Call,
        )
        and isinstance(
            root.func,
            ast.Name,
        )
        and root.func.id == "not_"
        and len(root.args) == 1
    ):
        raise ValueError("unexpected not_ expression")

    leaf = root.args[0]

    if not (
        isinstance(
            leaf,
            ast.Call,
        )
        and isinstance(
            leaf.func,
            ast.Name,
        )
        and leaf.func.id == "individu"
    ):
        raise ValueError("unexpected nested leaf")

    if not (
        leaf.args
        and isinstance(
            leaf.args[0],
            ast.Constant,
        )
        and leaf.args[0].value == "enfant_a_charge"
    ):
        raise ValueError("unexpected OpenFisca variable")

    enfant = z3.Bool("enfant_a_charge")

    source_expr = z3.Not(enfant)

    target_expr = z3.Not(enfant)

    mutant_expr = enfant

    correct = z3.Solver()

    correct.add(source_expr != target_expr)

    correct_status = correct.check()

    mutant = z3.Solver()

    mutant.add(source_expr != mutant_expr)

    mutant_status = mutant.check()

    return {
        "candidate_id": NOT_ID,
        "repair_kind": "NOT_OVER_DECLARATIVE_LEAF",
        "source_expression": expression,
        "leaf_binding": ("individu('enfant_a_charge', period.this_year)"),
        "required_contracts": ["not_"],
        "registry_evidence": {
            "not_": registry_evidence["not_"],
        },
        "correct_solver_status": str(correct_status),
        "mutant_solver_status": str(mutant_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_disproved": mutant_status == z3.sat,
        "passed": (correct_status == z3.unsat and mutant_status == z3.sat),
    }


proofs = [prove_where_min(cid) for cid in sorted(WHERE_MIN_IDS)]

proofs.append(prove_not_leaf())


for proof in proofs:
    if not proof["passed"]:
        raise ValueError("dependency repair proof failed: " + proof["candidate_id"])


proof_path = OUT / "dependency_repair_proofs.jsonl"

proof_path.write_text(
    "".join(
        json.dumps(
            proof,
            sort_keys=True,
        )
        + "\n"
        for proof in proofs
    ),
    encoding="utf-8",
)


# a74d cannot be repaired without adding
# new and_/or_ contracts to frozen V0.11.

a74 = decision_rows[RETRACT_ID]

global_and = registry_evidence["and_"]["match_count"]

global_or = registry_evidence["or_"]["match_count"]

supersession = {
    "candidate_id": RETRACT_ID,
    "previous_terminal_outcome": "CERTIFIED_A1",
    "corrected_terminal_outcome": "NOT_CERTIFIED_UNSUPPORTED",
    "reason_code": ("NESTED_AND_OR_HELPERS_OUTSIDE_FROZEN_A1_CONTRACT_CLOSURE"),
    "nested_semantic_helpers": a74["semantic_helpers"],
    "previous_declared_contracts": a74["declared_semantic_contracts"],
    "global_registry_and_matches": global_and,
    "global_registry_or_matches": global_or,
    "scope_extension_performed": False,
    "rationale": (
        "The prior A1 binding hides nested "
        "and_/or_ semantics not closed by the "
        "frozen V0.11 semantic-contract set. "
        "The candidate is conservatively "
        "reclassified rather than extending "
        "the formal scope after sampling."
    ),
}

supersession_path = OUT / "a74d_certificate_supersession.json"

supersession_path.write_text(
    json.dumps(
        supersession,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


rows = load_jsonl(LEDGER)

assert len(rows) == 90

updated = []


for row in rows:
    cid = row["candidate_id"]

    new_row = dict(row)

    if cid in REPAIRED_IDS:
        if row["terminal_outcome"] != "CERTIFIED_A1":
            raise ValueError("repair target no longer A1: " + cid)

        new_row["dependency_closure_status"] = "PROVED_RECURSIVE"

        new_row["dependency_closure_evidence"] = str(proof_path)

    elif cid == RETRACT_ID:
        if row["terminal_outcome"] != "CERTIFIED_A1":
            raise ValueError("a74d no longer A1")

        old_certificate = row.get("certificate_id")

        old_digest = row.get("certificate_digest")

        new_row["superseded_terminal_outcome"] = "CERTIFIED_A1"

        new_row["superseded_certificate_id"] = old_certificate

        new_row["superseded_certificate_digest"] = old_digest

        new_row["terminal_outcome"] = "NOT_CERTIFIED_UNSUPPORTED"

        new_row["reason_code"] = supersession["reason_code"]

        new_row["evidence_file"] = str(supersession_path)

        new_row["certificate_id"] = None

        if "certificate_digest" in new_row:
            new_row["certificate_digest"] = None

    updated.append(new_row)


dist = Counter(row["terminal_outcome"] for row in updated)

expected = {
    "CERTIFIED_A1": 33,
    "CERTIFIED_A2": 17,
    "NOT_CERTIFIED_SEMANTIC_AMBIGUITY": 2,
    "NOT_CERTIFIED_UNSUPPORTED": 38,
}

if dist != expected:
    raise ValueError("unexpected corrected distribution: " + repr(dict(dist)))


assert len(updated) == 90

assert all(row["state"] == "TERMINAL_ASSIGNED" for row in updated)


LEDGER.write_text(
    "".join(
        json.dumps(
            row,
            sort_keys=True,
        )
        + "\n"
        for row in updated
    ),
    encoding="utf-8",
)


summary = {
    "terminalized": 90,
    "pending": 0,
    "repaired_a1": sorted(REPAIRED_IDS),
    "reclassified": [RETRACT_ID],
    "distribution": dict(sorted(dist.items())),
    "scope_extension_performed": False,
}


(OUT / "repair_summary.json").write_text(
    json.dumps(
        summary,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


print(
    "recursive A1 repairs =",
    len(REPAIRED_IDS),
)

for proof in proofs:
    print()
    print(
        proof["candidate_id"],
        proof["repair_kind"],
    )

    print(
        " correct =",
        proof["correct_solver_status"],
    )

    print(
        " mutant  =",
        proof["mutant_solver_status"],
    )

    print(
        " passed  =",
        proof["passed"],
    )


print()
print(
    "reclassified unsupported =",
    RETRACT_ID,
)

print(
    "and_ registry matches    =",
    global_and,
)

print(
    "or_ registry matches     =",
    global_or,
)

print()
print("terminalized = 90/90")

print("pending      = 0/90")

print(
    "distribution =",
    dict(sorted(dist.items())),
)

print()
print("W11-C DEPENDENCY REPAIR: PASS")
