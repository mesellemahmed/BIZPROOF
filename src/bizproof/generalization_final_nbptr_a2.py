from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import random
import textwrap
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import z3

CID = "53abfcd7d20a9cd6"

EXPECTED_SHA = "653fd8c2ec5f05ffe7a827976c2ffc3e9d8755d74acaa61ebc692cc426844c88"

SOURCE = Path(
    "external_sources/v0.6/openfisca_france/"
    "openfisca_france/model/prelevements_obligatoires/"
    "impot_revenu/ir.py"
)

CLASS_NAME = "nbptr"
FUNCTION_NAME = "formula_2008_01_01"


INPUT_NAMES = (
    "nb_pac",
    "maries_ou_pacses",
    "celibataire_ou_divorce",
    "veuf",
    "jeune_veuf",
    "nbG",
    "nbH",
    "nbI",
    "nbR",
    "nbN",
    "caseP",
    "caseW",
    "caseG",
    "caseE",
    "caseK",
    "caseN",
    "caseF",
    "caseS",
    "caseL",
    "caseT",
)

BOOLEAN_INPUTS = {
    "maries_ou_pacses",
    "celibataire_ou_divorce",
    "veuf",
    "jeune_veuf",
    "caseP",
    "caseW",
    "caseG",
    "caseE",
    "caseK",
    "caseN",
    "caseF",
    "caseS",
    "caseL",
    "caseT",
}

COUNT_INPUTS = set(INPUT_NAMES) - BOOLEAN_INPUTS


PARAM_NAMES = (
    "cas_general.conj",
    "cas_general.enf1",
    "cas_general.enf2",
    "cas_general.enf3_et_sup",
    "cas_general.veuf",
    "couple_ou_pers_a_charge.inv1",
    "couple_ou_pers_a_charge.inv2",
    "couple_ou_pers_a_charge.isol",
    "couple_ou_pers_a_charge.not41",
    "couple_ou_pers_a_charge.not42",
    "couple_ou_pers_a_charge.not6",
    "sans_pers_a_charge.not31a",
    "sans_pers_a_charge.not31b",
    "sans_pers_a_charge.not32",
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _locked_function() -> tuple[ast.FunctionDef, str]:

    source = SOURCE.read_text(encoding="utf-8")

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

    fn = matches[0]

    segment = (
        ast.get_source_segment(
            source,
            fn,
        )
        or ""
    )

    digest = _sha256(segment)

    if digest != EXPECTED_SHA:
        raise ValueError(f"function SHA mismatch: {digest}")

    return fn, segment


def adapt_nbptr(
    v: dict[str, Any],
    q: dict[str, Any],
) -> Any:

    nb_pac = v["nb_pac"]

    maries_ou_pacses = v["maries_ou_pacses"]

    celibataire_ou_divorce = v["celibataire_ou_divorce"]

    veuf = v["veuf"]
    jeune_veuf = v["jeune_veuf"]

    nbG = v["nbG"]
    nbH = v["nbH"]
    nbI = v["nbI"]
    nbR = v["nbR"]

    caseP = v["caseP"]
    caseW = v["caseW"]
    caseG = v["caseG"]
    caseE = v["caseE"]
    caseK = v["caseK"]
    caseN = v["caseN"]
    caseF = v["caseF"]
    caseS = v["caseS"]
    caseL = v["caseL"]
    caseT = v["caseT"]

    no_pac = nb_pac == 0
    has_pac = not no_pac

    no_alt = nbH == 0
    has_alt = not no_alt

    enf_a = (
        (no_pac & has_alt)
        * (
            q["cas_general.enf1"] * min(nbH, 1)
            + q["cas_general.enf2"]
            * max(
                min(nbH - 1, 1),
                0,
            )
            + q["cas_general.enf3_et_sup"] * max(nbH - 2, 0)
        )
        * 0.5
    )

    enf_b = (has_pac & has_alt) * (
        (nb_pac == 1)
        * (q["cas_general.enf2"] * min(nbH, 1) + q["cas_general.enf3_et_sup"] * max(nbH - 1, 0))
        * 0.5
        + (nb_pac > 1) * (q["cas_general.enf3_et_sup"] * nbH * 0.5)
    )

    enf_c = (
        q["cas_general.enf1"] * min(nb_pac, 1)
        + q["cas_general.enf2"]
        * max(
            min(nb_pac - 1, 1),
            0,
        )
        + q["cas_general.enf3_et_sup"] * max(nb_pac - 2, 0)
    )

    enf = enf_a + enf_b + enf_c

    n2 = (
        q["couple_ou_pers_a_charge.inv1"] * (nbG + nbI / 2)
        + q["couple_ou_pers_a_charge.inv2"] * nbR
    )

    n31a = q["sans_pers_a_charge.not31a"] * (no_pac & no_alt & caseP)

    n31b = q["sans_pers_a_charge.not31b"] * (no_pac & no_alt & (caseW | caseG))

    n31 = max(
        n31a,
        n31b,
    )

    n32 = q["sans_pers_a_charge.not32"] * (
        no_pac & no_alt & ((caseE | caseK | caseL) & (not caseN))
    )

    n3 = max(
        n31,
        n32,
    )

    n4 = max(
        q["couple_ou_pers_a_charge.not41"] * (1 * caseP + 1 * caseF),
        q["couple_ou_pers_a_charge.not42"] * (caseW | caseS),
    )

    n5 = (
        q["couple_ou_pers_a_charge.isol"]
        * caseT
        * ((no_pac & has_alt) * ((nbH == 1) * 0.5 + (nbH >= 2)) + 1 * has_pac)
    )

    n6 = q["couple_ou_pers_a_charge.not6"] * (caseP & (has_pac | has_alt))

    n7 = (
        q["couple_ou_pers_a_charge.isol"]
        * caseT
        * ((no_pac & has_alt) * ((nbH == 1) * 0.5 + (nbH >= 2)) + 1 * has_pac)
    )

    nb_parts_famille = 1 + q["cas_general.conj"] + enf + n2 + n4

    nb_parts_veuf = 1 + q["cas_general.veuf"] * (has_pac | has_alt) + enf + n2 + n3 + n5 + n6

    nb_parts_celib = 1 + enf + n2 + n3 + n6 + n7

    return (
        (maries_ou_pacses | jeune_veuf) * nb_parts_famille
        + (veuf & (not jeune_veuf)) * nb_parts_veuf
        + celibataire_ou_divorce * nb_parts_celib
    )


def mutant_nbptr(
    v: dict[str, Any],
    q: dict[str, Any],
) -> Any:

    mutated = dict(v)

    mutated["caseL"] = 0

    return adapt_nbptr(
        mutated,
        q,
    )


def _source_callable() -> Any:

    fn, _ = _locked_function()

    clean = copy.deepcopy(fn)

    clean.decorator_list = []

    module = ast.Module(
        body=[clean],
        type_ignores=[],
    )

    ast.fix_missing_locations(module)

    namespace: dict[
        str,
        Any,
    ] = {
        "not_": lambda value: not value,
        "min_": min,
        "max_": max,
    }

    exec(
        compile(
            module,
            str(SOURCE),
            "exec",
        ),
        namespace,
    )

    return namespace[FUNCTION_NAME]


def _parameters(
    q: dict[str, Any],
) -> Any:

    qf = SimpleNamespace(
        cas_general=SimpleNamespace(
            conj=q["cas_general.conj"],
            enf1=q["cas_general.enf1"],
            enf2=q["cas_general.enf2"],
            enf3_et_sup=q["cas_general.enf3_et_sup"],
            veuf=q["cas_general.veuf"],
        ),
        couple_ou_pers_a_charge=SimpleNamespace(
            inv1=q["couple_ou_pers_a_charge.inv1"],
            inv2=q["couple_ou_pers_a_charge.inv2"],
            isol=q["couple_ou_pers_a_charge.isol"],
            not41=q["couple_ou_pers_a_charge.not41"],
            not42=q["couple_ou_pers_a_charge.not42"],
            not6=q["couple_ou_pers_a_charge.not6"],
        ),
        sans_pers_a_charge=SimpleNamespace(
            not31a=q["sans_pers_a_charge.not31a"],
            not31b=q["sans_pers_a_charge.not31b"],
            not32=q["sans_pers_a_charge.not32"],
        ),
    )

    return SimpleNamespace(
        impot_revenu=SimpleNamespace(
            calcul_impot_revenu=SimpleNamespace(plaf_qf=SimpleNamespace(quotient_familial=qf))
        )
    )


def _external(
    function: Any,
    v: dict[str, Any],
    q: dict[str, Any],
) -> Any:

    def lookup(
        name: str,
        _period: object,
    ) -> Any:
        return v[name]

    params = _parameters(q)

    def parameters(
        _period: object,
    ) -> Any:
        return params

    return function(
        lookup,
        object(),
        parameters,
    )


def _runtime_cases() -> list[
    tuple[
        dict[str, Any],
        dict[str, Any],
    ]
]:

    zero_v = {name: 0 for name in INPUT_NAMES}

    zero_q = {name: 0.0 for name in PARAM_NAMES}

    witness_v = dict(zero_v)

    witness_q = dict(zero_q)

    witness_v.update(
        {
            "celibataire_ou_divorce": 1,
            "caseL": 1,
        }
    )

    witness_q["sans_pers_a_charge.not32"] = 1.0

    cases = [
        (
            witness_v,
            witness_q,
        )
    ]

    rng = random.Random(20260929)

    q_values = (
        0.0,
        0.25,
        0.5,
        1.0,
        1.5,
        2.0,
    )

    for _ in range(512):
        v: dict[
            str,
            Any,
        ] = {}

        for name in INPUT_NAMES:
            if name in BOOLEAN_INPUTS:
                v[name] = rng.randint(
                    0,
                    1,
                )
            else:
                v[name] = rng.randint(
                    0,
                    5,
                )

        q = {name: rng.choice(q_values) for name in PARAM_NAMES}

        cases.append(
            (
                v,
                q,
            )
        )

    return cases


def runtime_evidence() -> dict[str, Any]:

    function = _source_callable()

    comparisons = 0

    adapter_mismatches = 0
    mutant_mismatches = 0

    first_adapter = None
    first_mutant = None

    for v, q in _runtime_cases():
        external = _external(
            function,
            v,
            q,
        )

        adapter = adapt_nbptr(
            v,
            q,
        )

        mutant = mutant_nbptr(
            v,
            q,
        )

        comparisons += 1

        if external != adapter:
            adapter_mismatches += 1

            if first_adapter is None:
                first_adapter = {
                    "v": v,
                    "q": q,
                    "external": external,
                    "adapter": adapter,
                }

        if external != mutant:
            mutant_mismatches += 1

            if first_mutant is None:
                first_mutant = {
                    "v": v,
                    "q": q,
                    "external": external,
                    "mutant": mutant,
                }

    return {
        "candidate_id": CID,
        "function_sha256": EXPECTED_SHA,
        "comparisons": comparisons,
        "adapter_mismatches": adapter_mismatches,
        "mutant_mismatches": mutant_mismatches,
        "first_adapter_mismatch": first_adapter,
        "first_mutant_mismatch": first_mutant,
        "source_execution_established": True,
        "adapter_preserved": adapter_mismatches == 0,
        "mutant_sensitive": mutant_mismatches > 0,
        "certification_claim": False,
        "passed": adapter_mismatches == 0 and mutant_mismatches > 0,
    }


def _attr_path(
    node: ast.Attribute,
) -> str | None:

    parts = [node.attr]

    current: ast.expr = node.value

    while isinstance(
        current,
        ast.Attribute,
    ):
        parts.append(current.attr)

        current = current.value

    if not isinstance(
        current,
        ast.Name,
    ):
        return None

    parts.append(current.id)

    return ".".join(reversed(parts))


class Translator:
    def __init__(self) -> None:

        self.inputs = {name: z3.Real("v_" + name) for name in INPUT_NAMES}

        self.params = {
            name: z3.Real(
                "q_"
                + name.replace(
                    ".",
                    "_",
                )
            )
            for name in PARAM_NAMES
        }

        self.env: dict[
            str,
            Any,
        ] = {}

    @staticmethod
    def b01(
        condition: Any,
    ) -> Any:

        return z3.If(
            condition,
            z3.RealVal(1),
            z3.RealVal(0),
        )

    def booleanize(
        self,
        value: Any,
    ) -> Any:

        return value != 0

    def expr(
        self,
        node: ast.expr,
    ) -> Any:

        if isinstance(
            node,
            ast.Name,
        ):
            if node.id in self.env:
                return self.env[node.id]

            raise ValueError("unknown name: " + node.id)

        if isinstance(
            node,
            ast.Constant,
        ):
            if isinstance(
                node.value,
                bool,
            ):
                return z3.RealVal(int(node.value))

            if isinstance(
                node.value,
                (int, float),
            ):
                return z3.RealVal(str(node.value))

            if isinstance(
                node.value,
                str,
            ):
                return node.value

            raise ValueError("unsupported constant")

        if isinstance(
            node,
            ast.Subscript,
        ):
            if not isinstance(
                node.value,
                ast.Name,
            ):
                raise ValueError("unsupported subscript root")

            key = self.expr(node.slice)

            if not isinstance(
                key,
                str,
            ):
                raise ValueError("non-string key")

            if node.value.id == "v":
                return self.inputs[key]

            if node.value.id == "q":
                return self.params[key]

            raise ValueError("unsupported mapping")

        if isinstance(
            node,
            ast.Attribute,
        ):
            path = _attr_path(node)

            if path is None:
                raise ValueError("unsupported attribute")

            prefix = "quotient_familial."

            if path.startswith(prefix):
                key = path[len(prefix) :]

                return self.params[key]

            raise ValueError("unsupported attribute path: " + path)

        if isinstance(
            node,
            ast.Call,
        ):
            if isinstance(
                node.func,
                ast.Name,
            ):
                name = node.func.id

                if name == "foyer_fiscal":
                    key = self.expr(node.args[0])

                    if not isinstance(
                        key,
                        str,
                    ):
                        raise ValueError("dynamic lookup")

                    return self.inputs[key]

                if name in {
                    "not_",
                }:
                    value = self.expr(node.args[0])

                    return self.b01(value == 0)

                if name in {
                    "min_",
                    "min",
                }:
                    left = self.expr(node.args[0])

                    right = self.expr(node.args[1])

                    return z3.If(
                        left <= right,
                        left,
                        right,
                    )

                if name in {
                    "max_",
                    "max",
                }:
                    left = self.expr(node.args[0])

                    right = self.expr(node.args[1])

                    return z3.If(
                        left >= right,
                        left,
                        right,
                    )

            raise ValueError("unsupported call")

        if isinstance(
            node,
            ast.UnaryOp,
        ):
            value = self.expr(node.operand)

            if isinstance(
                node.op,
                ast.Not,
            ):
                return self.b01(value == 0)

            if isinstance(
                node.op,
                ast.USub,
            ):
                return -value

            raise ValueError("unsupported unary operator")

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

            if isinstance(
                node.op,
                ast.Div,
            ):
                return left / right

            if isinstance(
                node.op,
                ast.BitAnd,
            ):
                return self.b01(
                    z3.And(
                        self.booleanize(left),
                        self.booleanize(right),
                    )
                )

            if isinstance(
                node.op,
                ast.BitOr,
            ):
                return self.b01(
                    z3.Or(
                        self.booleanize(left),
                        self.booleanize(right),
                    )
                )

            raise ValueError("unsupported binary operator")

        if isinstance(
            node,
            ast.Compare,
        ):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise ValueError("chained comparison")

            left = self.expr(node.left)

            right = self.expr(node.comparators[0])

            op = node.ops[0]

            if isinstance(
                op,
                ast.Eq,
            ):
                condition = left == right

            elif isinstance(
                op,
                ast.Gt,
            ):
                condition = left > right

            elif isinstance(
                op,
                ast.GtE,
            ):
                condition = left >= right

            elif isinstance(
                op,
                ast.Lt,
            ):
                condition = left < right

            elif isinstance(
                op,
                ast.LtE,
            ):
                condition = left <= right

            else:
                raise ValueError("unsupported comparison")

            return self.b01(condition)

        raise ValueError("unsupported AST node: " + type(node).__name__)

    def translate(
        self,
        fn: ast.FunctionDef,
        *,
        source_mode: bool,
    ) -> Any:

        result = None

        for statement in fn.body:
            if isinstance(
                statement,
                ast.Expr,
            ):
                continue

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

                if source_mode and name == "quotient_familial":
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
            raise ValueError("no return")

        return result


def _adapter_ast() -> ast.FunctionDef:

    text = textwrap.dedent(inspect.getsource(adapt_nbptr))

    tree = ast.parse(text)

    fn = tree.body[0]

    if not isinstance(
        fn,
        ast.FunctionDef,
    ):
        raise TypeError("adapter source is not function")

    return fn


def symbolic_evidence() -> dict[str, Any]:

    source_fn, _ = _locked_function()

    translator_source = Translator()

    source_expr = translator_source.translate(
        source_fn,
        source_mode=True,
    )

    translator_adapter = Translator()

    adapter_expr = translator_adapter.translate(
        _adapter_ast(),
        source_mode=False,
    )

    substitutions = []

    for name in INPUT_NAMES:
        substitutions.append(
            (
                translator_adapter.inputs[name],
                translator_source.inputs[name],
            )
        )

    for name in PARAM_NAMES:
        substitutions.append(
            (
                translator_adapter.params[name],
                translator_source.params[name],
            )
        )

    adapter_expr = z3.substitute(
        adapter_expr,
        *substitutions,
    )

    constraints = []

    for name in BOOLEAN_INPUTS:
        symbol = translator_source.inputs[name]

        constraints.append(
            z3.Or(
                symbol == 0,
                symbol == 1,
            )
        )

    for name in COUNT_INPUTS:
        symbol = translator_source.inputs[name]

        constraints.extend(
            [
                symbol >= 0,
                z3.IsInt(symbol),
            ]
        )

    for symbol in translator_source.params.values():
        constraints.append(symbol >= 0)

    correct = z3.Solver()

    correct.add(*constraints)

    correct.add(source_expr != adapter_expr)

    correct_status = correct.check()

    case_l = translator_source.inputs["caseL"]

    mutant_expr = z3.substitute(
        adapter_expr,
        (
            case_l,
            z3.RealVal(0),
        ),
    )

    mutant = z3.Solver()

    mutant.add(*constraints)

    mutant.add(source_expr != mutant_expr)

    mutant_status = mutant.check()

    witness = None

    if mutant_status == z3.sat:
        model = mutant.model()

        keys = (
            "nb_pac",
            "nbH",
            "celibataire_ou_divorce",
            "caseE",
            "caseK",
            "caseL",
            "caseN",
        )

        witness = {
            key: str(
                model.eval(
                    translator_source.inputs[key],
                    model_completion=True,
                )
            )
            for key in keys
        }

        witness["not32"] = str(
            model.eval(
                translator_source.params["sans_pers_a_charge.not32"],
                model_completion=True,
            )
        )

    return {
        "candidate_id": CID,
        "function_sha256": EXPECTED_SHA,
        "semantic_domain": (
            "Boolean source flags in {0,1}; "
            "count inputs are nonnegative integers; "
            "quotient-familial parameters are "
            "nonnegative rationals."
        ),
        "correct_solver_status": str(correct_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_solver_status": str(mutant_status),
        "mutant_disproved": mutant_status == z3.sat,
        "mutant_counterexample": witness,
        "certification_claim": False,
        "passed": (correct_status == z3.unsat and mutant_status == z3.sat),
    }


def _digest_json(
    value: Any,
) -> str:

    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run() -> int:

    out = Path("benchmarks/v0.11/final_a2_frontier/nbptr_a2")

    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    runtime = runtime_evidence()

    symbolic = symbolic_evidence()

    runtime_path = out / "runtime_evidence.json"

    symbolic_path = out / "symbolic_proof.json"

    runtime_path.write_text(
        json.dumps(
            runtime,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    symbolic_path.write_text(
        json.dumps(
            symbolic,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "runtime comparisons :",
        runtime["comparisons"],
    )

    print(
        "adapter mismatches  :",
        runtime["adapter_mismatches"],
    )

    print(
        "mutant mismatches   :",
        runtime["mutant_mismatches"],
    )

    print(
        "correct solver      :",
        symbolic["correct_solver_status"],
    )

    print(
        "mutant solver       :",
        symbolic["mutant_solver_status"],
    )

    all_pass = runtime["passed"] and symbolic["passed"]

    print(
        "W10-E A2 GATE       :",
        ("PASS" if all_pass else "FAIL"),
    )

    if not all_pass:
        return 1

    certificate: dict[str, Any] = {
        "schema_version": "BIZPROOF-V0.11-A2-CERTIFICATE-1",
        "candidate_id": CID,
        "terminal_outcome": "CERTIFIED_A2",
        "assistance_level": "A2",
        "authoring_mode": "EXPLICIT_HUMAN_AUTHORED_SCALAR_ADAPTER",
        "function_sha256": EXPECTED_SHA,
        "adapter_function": "adapt_nbptr",
        "adapter_sha256": _sha256(inspect.getsource(adapt_nbptr)),
        "runtime_evidence": runtime,
        "symbolic_evidence": symbolic,
        "claim_scope": (
            "Locked OpenFisca nbptr.formula_2008_01_01 "
            "scalar semantics over the declared "
            "boolean/count/quotient-family parameter domain."
        ),
        "certification_claim": True,
    }

    certificate_digest = _digest_json(certificate)

    certificate["certificate_digest"] = certificate_digest

    certificate["certificate_id"] = "CERT-V011-A2-" + certificate_digest[:16].upper()

    cert_path = out / (certificate["certificate_id"] + ".json")

    cert_path.write_text(
        json.dumps(
            certificate,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    ledger_path = Path("benchmarks/v0.11/controlled_complex_closure/candidate_terminal_state.jsonl")

    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    before_pending = [row for row in rows if row["state"] == "PENDING_UNASSIGNED"]

    if len(before_pending) != 1 or before_pending[0]["candidate_id"] != CID:
        raise ValueError("unexpected pre-closure ledger")

    updated = []

    for row in rows:
        if row["candidate_id"] != CID:
            updated.append(row)

            continue

        new_row = dict(row)

        new_row.update(
            {
                "state": "TERMINAL_ASSIGNED",
                "terminal_outcome": "CERTIFIED_A2",
                "certificate_id": certificate["certificate_id"],
                "certificate_digest": certificate_digest,
                "evidence_file": str(cert_path),
            }
        )

        updated.append(new_row)

    terminal = [row for row in updated if row["state"] == "TERMINAL_ASSIGNED"]

    pending = [row for row in updated if row["state"] == "PENDING_UNASSIGNED"]

    distribution = Counter(row["terminal_outcome"] for row in terminal)

    expected = {
        "CERTIFIED_A1": 34,
        "CERTIFIED_A2": 17,
        "NOT_CERTIFIED_SEMANTIC_AMBIGUITY": 2,
        "NOT_CERTIFIED_UNSUPPORTED": 37,
    }

    if len(terminal) != 90:
        raise ValueError("terminal count != 90")

    if pending:
        raise ValueError("pending candidates remain")

    if distribution != expected:
        raise ValueError("unexpected distribution: " + repr(dict(distribution)))

    ledger_path.write_text(
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

    print()
    print(
        "certificate          :",
        certificate["certificate_id"],
    )

    print("terminalized         : 90/90")

    print("pending              : 0/90")

    print(
        "distribution         :",
        dict(sorted(distribution.items())),
    )

    print("W10-E FINAL CLOSURE  : PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
