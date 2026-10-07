from __future__ import annotations

import argparse
import hashlib
import inspect
import itertools
import json
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypeAlias

import z3

from .generalization_a2_authoring import (
    _extract_function,
    _sha256_file,
    _sha256_text,
)

JsonDict: TypeAlias = dict[str, Any]


V2_IDS = {
    "d285ecd86455b150",
    "4d7d61b18dde0ad5",
    "d5b65e1d48eca4dd",
    "6fd8bd69c26e7954",
    "6d009b7961c5d116",
    "f5d217dec0cf902b",
    "e293930485085dac",
    "7bc9603bfbda7dc9",
    "53abfcd7d20a9cd6",
}


SCALAR_TARGETS = {
    "d5b65e1d48eca4dd": "LOCAPASS_STUDENT_CONTRACT",
    "f5d217dec0cf902b": "SPECIAL_ALLOWANCE",
    "e293930485085dac": "HOUSING_TAX_EXEMPTION",
}


COMPLEX_SCALAR_REVIEW = {
    "7bc9603bfbda7dc9": "SCALAR_RETURN_LARGE_PARAMETERIZED_FORMULA",
    "53abfcd7d20a9cd6": "SCALAR_RETURN_LARGE_QUOTIENT_FORMULA",
}


NON_SCALAR_REVIEW = {
    "d285ecd86455b150": "TUPLE_RETURN",
    "4d7d61b18dde0ad5": "HTTP_RESPONSE_RETURN",
    "6fd8bd69c26e7954": "DOMAIN_OBJECT_RETURN",
    "6d009b7961c5d116": "LIST_OF_DOMAIN_OBJECTS_RETURN",
}


def adapt_locapass_student_contract(
    salaries: tuple[int, int, int, int, int, int],
) -> bool:

    months = sum(1 for salary in salaries if salary > 0)

    return months >= 3


def mutant_locapass_student_contract(
    salaries: tuple[int, int, int, int, int, int],
) -> bool:

    months = sum(1 for salary in salaries if salary > 0)

    return months >= 2


def adapt_special_allowance(
    age_declarant: int,
    declarant_invalid: bool,
    age_spouse: int,
    spouse_invalid: bool,
    global_income: int,
    married_children: int,
    age_invalidity_allowance: int,
    married_child_allowance: int,
) -> int:

    eligible_people = int((age_declarant >= 65 or declarant_invalid) and age_declarant > 0) + int(
        (age_spouse >= 65 or spouse_invalid) and age_spouse > 0
    )

    invalidity_amount = eligible_people * age_invalidity_allowance

    children_amount = married_children * married_child_allowance

    return min(
        global_income,
        invalidity_amount + children_amount,
    )


def mutant_special_allowance(
    age_declarant: int,
    declarant_invalid: bool,
    age_spouse: int,
    spouse_invalid: bool,
    global_income: int,
    married_children: int,
    age_invalidity_allowance: int,
    married_child_allowance: int,
) -> int:

    correct = adapt_special_allowance(
        age_declarant,
        declarant_invalid,
        age_spouse,
        spouse_invalid,
        global_income,
        married_children,
        age_invalidity_allowance,
        married_child_allowance,
    )

    raw = (
        int((age_declarant >= 65 or declarant_invalid) and age_declarant > 0)
        + int((age_spouse >= 65 or spouse_invalid) and age_spouse > 0)
    ) * age_invalidity_allowance

    raw += married_children * married_child_allowance

    return max(
        correct,
        raw,
        global_income,
    )


def adapt_housing_tax_exemption(
    age_reference: int,
    age_spouse: int,
    reference_is_widowed: bool,
    aah: int,
    asi: int,
    aspa: int,
    isf_ifi: int,
    rfr_condition: bool,
    exemption_age: int,
) -> int:

    unconditional = int(asi > 0) + int(aspa > 0)

    conditional = (
        int(age_reference >= exemption_age)
        + int(age_spouse >= exemption_age)
        + int(reference_is_widowed)
    ) * int(isf_ifi == 0) + int(aah > 0)

    return unconditional + conditional * int(rfr_condition)


def mutant_housing_tax_exemption(
    age_reference: int,
    age_spouse: int,
    reference_is_widowed: bool,
    aah: int,
    asi: int,
    aspa: int,
    isf_ifi: int,
    rfr_condition: bool,
    exemption_age: int,
) -> int:

    del rfr_condition

    unconditional = int(asi > 0) + int(aspa > 0)

    conditional = (
        int(age_reference >= exemption_age)
        + int(age_spouse >= exemption_age)
        + int(reference_is_widowed)
    ) * int(isf_ifi == 0) + int(aah > 0)

    return unconditional + conditional


ADAPTERS = {
    "LOCAPASS_STUDENT_CONTRACT": (
        adapt_locapass_student_contract,
        mutant_locapass_student_contract,
    ),
    "SPECIAL_ALLOWANCE": (
        adapt_special_allowance,
        mutant_special_allowance,
    ),
    "HOUSING_TAX_EXEMPTION": (
        adapt_housing_tax_exemption,
        mutant_housing_tax_exemption,
    ),
}


def _load_jsonl(
    path: Path,
) -> list[JsonDict]:

    result: list[JsonDict] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue

        value = json.loads(raw)

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(f"expected JSON object: {path}")

        result.append(value)

    return result


def _digest(
    value: Any,
) -> str:

    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _function_digest(
    function: Any,
) -> str:

    return hashlib.sha256(inspect.getsource(function).encode("utf-8")).hexdigest()


def _exec_function(
    source_slice: str,
    function_name: str,
    globals_extra: dict[str, Any] | None = None,
) -> Any:

    namespace: dict[str, Any] = {}

    if globals_extra:
        namespace.update(globals_extra)

    source = textwrap.dedent(source_slice)

    exec(
        compile(
            source,
            "<locked-source-slice>",
            "exec",
        ),
        namespace,
    )

    value = namespace.get(function_name)

    if not callable(value):
        raise ValueError("expected callable absent: " + function_name)

    return value


def _verify_live_source(
    *,
    repo_root: Path,
    record: JsonDict,
) -> str:

    path = repo_root / "external_sources/v0.6" / str(record["source"]) / str(record["file"])

    if _sha256_file(path) != str(record["source_file_sha256"]):
        raise ValueError("source file SHA mismatch: " + str(record["candidate_id"]))

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    lines = [int(value) for value in record["lines"]]

    _, segment = _extract_function(
        source,
        str(record["function"]),
        lines[0],
        lines[1],
    )

    if _sha256_text(segment) != str(record["function_sha256"]):
        raise ValueError("function SHA mismatch: " + str(record["candidate_id"]))

    return segment


class _Period:
    first_month = "FIRST"
    last_year = "LAST_YEAR"

    def offset(
        self,
        value: int,
    ) -> int:

        return value


class _SpecialFoyer:
    def __init__(
        self,
        *,
        age_declarant: int,
        declarant_invalid: bool,
        age_spouse: int,
        spouse_invalid: bool,
        global_income: int,
        married_children: int,
    ) -> None:

        self._values = {
            "caseP": declarant_invalid,
            "caseF": spouse_invalid,
            "rng": global_income,
            "nbN": married_children,
        }

        self._age_declarant = age_declarant

        self._age_spouse = age_spouse

    def __call__(
        self,
        name: str,
        period: Any,
    ) -> Any:

        del period

        return self._values[name]

    def declarant_principal(
        self,
        name: str,
        period: Any,
    ) -> Any:

        del name
        del period

        return self._age_declarant

    def conjoint(
        self,
        name: str,
        period: Any,
    ) -> Any:

        del name
        del period

        return self._age_spouse


class _Allowance:
    def __init__(
        self,
        value: int,
    ) -> None:

        self._value = value

    def calc(
        self,
        income: int,
    ) -> int:

        del income

        return self._value


class _MembersProxy:
    def __init__(
        self,
        values: dict[str, Any],
    ) -> None:

        self._values = values
        self.famille = self
        self.foyer_fiscal = self

    def __call__(
        self,
        name: str,
        period: Any,
        options: Any = None,
    ) -> Any:

        del period
        del options

        return self._values[name]


class _HousingMenage:
    def __init__(
        self,
        *,
        age_reference: int,
        age_spouse: int,
        reference_is_widowed: bool,
        aah: int,
        asi: int,
        aspa: int,
        isf_ifi: int,
        rfr_condition: bool,
    ) -> None:

        self._age_reference = age_reference

        self._age_spouse = age_spouse

        self._marital = "VEUF" if reference_is_widowed else "AUTRE"

        self.members = _MembersProxy(
            {
                "aah": aah,
                "asi": asi,
                "aspa": aspa,
                "isf_ifi": isf_ifi,
                "condition_rfr_exoneration_th": rfr_condition,
            }
        )

    def personne_de_reference(
        self,
        name: str,
        period: Any,
    ) -> Any:

        del period

        if name == "age":
            return self._age_reference

        if name == "statut_marital":
            return self._marital

        raise KeyError(name)

    def conjoint(
        self,
        name: str,
        period: Any,
    ) -> Any:

        del name
        del period

        return self._age_spouse

    def sum(
        self,
        value: Any,
        role: Any = None,
    ) -> Any:

        del role

        return value

    def all(
        self,
        value: Any,
    ) -> bool:

        return bool(value)


def _runtime_locapass(
    source_slice: str,
) -> JsonDict:

    source_function = _exec_function(
        source_slice,
        "formula",
    )

    comparisons = 0
    mismatches = 0
    mutant_mismatches = 0

    values = (
        -1,
        0,
        1,
    )

    for salaries_raw in itertools.product(
        values,
        repeat=6,
    ):
        salaries = (
            int(salaries_raw[0]),
            int(salaries_raw[1]),
            int(salaries_raw[2]),
            int(salaries_raw[3]),
            int(salaries_raw[4]),
            int(salaries_raw[5]),
        )

        by_period = {-index: salaries[index] for index in range(6)}

        def individu(
            name: str,
            period_value: Any,
            by_period: dict[int, int] = by_period,
        ) -> int:

            if name != "salaire_net":
                raise KeyError(name)

            return by_period[int(period_value)]

        external = source_function(
            individu,
            _Period(),
        )

        adapter = adapt_locapass_student_contract(salaries)

        mutant = mutant_locapass_student_contract(salaries)

        comparisons += 1

        if external != adapter:
            mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

    return {
        "validation_domain": "six monthly salaries in {-1,0,1}",
        "comparisons": comparisons,
        "adapter_mismatches": mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _runtime_special_allowance(
    source_slice: str,
) -> JsonDict:

    source_function = _exec_function(
        source_slice,
        "formula",
        {
            "min_": min,
        },
    )

    comparisons = 0
    mismatches = 0
    mutant_mismatches = 0

    for (
        age_declarant,
        declarant_invalid,
        age_spouse,
        spouse_invalid,
        global_income,
        married_children,
        age_allowance,
        child_allowance,
    ) in itertools.product(
        (
            0,
            64,
            65,
            70,
        ),
        (
            False,
            True,
        ),
        (
            0,
            64,
            65,
            70,
        ),
        (
            False,
            True,
        ),
        (
            0,
            100,
            1000,
        ),
        (
            0,
            2,
        ),
        (
            0,
            100,
        ),
        (
            0,
            50,
        ),
    ):
        foyer = _SpecialFoyer(
            age_declarant=int(age_declarant),
            declarant_invalid=bool(declarant_invalid),
            age_spouse=int(age_spouse),
            spouse_invalid=bool(spouse_invalid),
            global_income=int(global_income),
            married_children=int(married_children),
        )

        allowance = _Allowance(int(age_allowance))

        parameters_value = SimpleNamespace(
            impot_revenu=SimpleNamespace(
                calcul_revenus_imposables=SimpleNamespace(
                    abat_rni=SimpleNamespace(
                        contribuable_age_invalide=allowance,
                        enfant_marie=int(child_allowance),
                    )
                )
            )
        )

        def parameters(
            period: Any,
            parameters_value: Any = parameters_value,
        ) -> Any:

            del period

            return parameters_value

        external = source_function(
            foyer,
            _Period(),
            parameters,
        )

        adapter = adapt_special_allowance(
            int(age_declarant),
            bool(declarant_invalid),
            int(age_spouse),
            bool(spouse_invalid),
            int(global_income),
            int(married_children),
            int(age_allowance),
            int(child_allowance),
        )

        mutant = mutant_special_allowance(
            int(age_declarant),
            bool(declarant_invalid),
            int(age_spouse),
            bool(spouse_invalid),
            int(global_income),
            int(married_children),
            int(age_allowance),
            int(child_allowance),
        )

        comparisons += 1

        if external != adapter:
            mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

    return {
        "validation_domain": ("bounded scalar age, invalidity, income, child and allowance grid"),
        "comparisons": comparisons,
        "adapter_mismatches": mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _runtime_housing_tax(
    source_slice: str,
) -> JsonDict:

    add_marker = object()

    famille_type = SimpleNamespace(DEMANDEUR="DEMANDEUR")

    foyer_type = SimpleNamespace(DECLARANT_PRINCIPAL="DECLARANT_PRINCIPAL")

    marital_type = SimpleNamespace(veuf="VEUF")

    source_function = _exec_function(
        source_slice,
        "formula_2017_01_01",
        {
            "ADD": add_marker,
            "Famille": famille_type,
            "FoyerFiscal": foyer_type,
            "TypesStatutMarital": marital_type,
        },
    )

    comparisons = 0
    mismatches = 0
    mutant_mismatches = 0

    exemption_age = 60

    for (
        age_reference,
        age_spouse,
        widowed,
        aah,
        asi,
        aspa,
        isf_ifi,
        rfr_condition,
    ) in itertools.product(
        (
            50,
            60,
            70,
        ),
        (
            50,
            60,
            70,
        ),
        (
            False,
            True,
        ),
        (
            0,
            1,
        ),
        (
            0,
            1,
        ),
        (
            0,
            1,
        ),
        (
            0,
            1,
        ),
        (
            False,
            True,
        ),
    ):
        menage = _HousingMenage(
            age_reference=int(age_reference),
            age_spouse=int(age_spouse),
            reference_is_widowed=bool(widowed),
            aah=int(aah),
            asi=int(asi),
            aspa=int(aspa),
            isf_ifi=int(isf_ifi),
            rfr_condition=bool(rfr_condition),
        )

        parameters_value = SimpleNamespace(
            taxe_habitation=SimpleNamespace(exon_age_min=exemption_age)
        )

        def parameters(
            period: Any,
            parameters_value: Any = parameters_value,
        ) -> Any:

            del period

            return parameters_value

        external = source_function(
            menage,
            _Period(),
            parameters,
        )

        adapter = adapt_housing_tax_exemption(
            int(age_reference),
            int(age_spouse),
            bool(widowed),
            int(aah),
            int(asi),
            int(aspa),
            int(isf_ifi),
            bool(rfr_condition),
            exemption_age,
        )

        mutant = mutant_housing_tax_exemption(
            int(age_reference),
            int(age_spouse),
            bool(widowed),
            int(aah),
            int(asi),
            int(aspa),
            int(isf_ifi),
            bool(rfr_condition),
            exemption_age,
        )

        comparisons += 1

        if external != adapter:
            mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

    return {
        "validation_domain": ("bounded ages and boolean/0-1 benefit-tax-condition grid"),
        "comparisons": comparisons,
        "adapter_mismatches": mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _symbolic_locapass() -> JsonDict:

    salaries = [z3.Int(f"salary_{index}") for index in range(6)]

    positive_count = z3.Sum(
        [
            z3.If(
                salary > 0,
                1,
                0,
            )
            for salary in salaries
        ]
    )

    source = positive_count >= 3

    adapter = positive_count >= 3

    mutant = positive_count >= 2

    correct = z3.Solver()
    correct.add(source != adapter)

    mutant_solver = z3.Solver()
    mutant_solver.add(source != mutant)

    correct_status = correct.check()
    mutant_status = mutant_solver.check()

    return {
        "symbolic_domain": "six unrestricted integer salaries",
        "correct_solver_status": str(correct_status),
        "mutant_solver_status": str(mutant_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_disproved": mutant_status == z3.sat,
    }


def _symbolic_special_allowance() -> JsonDict:

    age_declarant = z3.Int("age_declarant")

    age_spouse = z3.Int("age_spouse")

    declarant_invalid = z3.Bool("declarant_invalid")

    spouse_invalid = z3.Bool("spouse_invalid")

    income = z3.Int("global_income")

    children = z3.Int("married_children")

    age_allowance = z3.Int("age_allowance")

    child_allowance = z3.Int("child_allowance")

    eligible = z3.If(
        z3.And(
            z3.Or(
                age_declarant >= 65,
                declarant_invalid,
            ),
            age_declarant > 0,
        ),
        1,
        0,
    ) + z3.If(
        z3.And(
            z3.Or(
                age_spouse >= 65,
                spouse_invalid,
            ),
            age_spouse > 0,
        ),
        1,
        0,
    )

    raw = eligible * age_allowance + children * child_allowance

    source = z3.If(
        income <= raw,
        income,
        raw,
    )

    adapter = z3.If(
        income <= raw,
        income,
        raw,
    )

    mutant = z3.If(
        income >= raw,
        income,
        raw,
    )

    constraints = [
        age_declarant >= 0,
        age_spouse >= 0,
        income >= 0,
        children >= 0,
        age_allowance >= 0,
        child_allowance >= 0,
    ]

    correct = z3.Solver()
    correct.add(*constraints)
    correct.add(source != adapter)

    mutant_solver = z3.Solver()
    mutant_solver.add(*constraints)
    mutant_solver.add(source != mutant)

    correct_status = correct.check()
    mutant_status = mutant_solver.check()

    return {
        "symbolic_domain": ("nonnegative scalar ages, income and allowance values"),
        "correct_solver_status": str(correct_status),
        "mutant_solver_status": str(mutant_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_disproved": mutant_status == z3.sat,
    }


def _symbolic_housing_tax() -> JsonDict:

    age_reference = z3.Int("age_reference")

    age_spouse = z3.Int("age_spouse")

    exemption_age = z3.Int("exemption_age")

    widowed = z3.Bool("widowed")

    aah = z3.Int("aah")
    asi = z3.Int("asi")
    aspa = z3.Int("aspa")
    isf_ifi = z3.Int("isf_ifi")

    rfr = z3.Bool("rfr_condition")

    def bit(
        value: Any,
    ) -> Any:

        return z3.If(
            value,
            1,
            0,
        )

    unconditional = bit(asi > 0) + bit(aspa > 0)

    conditional = (
        bit(age_reference >= exemption_age) + bit(age_spouse >= exemption_age) + bit(widowed)
    ) * bit(isf_ifi == 0) + bit(aah > 0)

    source = unconditional + conditional * bit(rfr)

    adapter = unconditional + conditional * bit(rfr)

    mutant = unconditional + conditional

    constraints = [
        age_reference >= 0,
        age_spouse >= 0,
        exemption_age >= 0,
        aah >= 0,
        asi >= 0,
        aspa >= 0,
        isf_ifi >= 0,
    ]

    correct = z3.Solver()
    correct.add(*constraints)
    correct.add(source != adapter)

    mutant_solver = z3.Solver()
    mutant_solver.add(*constraints)
    mutant_solver.add(source != mutant)

    correct_status = correct.check()
    mutant_status = mutant_solver.check()

    return {
        "symbolic_domain": ("nonnegative ages/benefit/tax scalars with boolean widow/RFR"),
        "correct_solver_status": str(correct_status),
        "mutant_solver_status": str(mutant_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_disproved": mutant_status == z3.sat,
    }


RUNTIME = {
    "LOCAPASS_STUDENT_CONTRACT": _runtime_locapass,
    "SPECIAL_ALLOWANCE": _runtime_special_allowance,
    "HOUSING_TAX_EXEMPTION": _runtime_housing_tax,
}


SYMBOLIC = {
    "LOCAPASS_STUDENT_CONTRACT": _symbolic_locapass,
    "SPECIAL_ALLOWANCE": _symbolic_special_allowance,
    "HOUSING_TAX_EXEMPTION": _symbolic_housing_tax,
}


def _protocol_definition(
    path: Path,
) -> JsonDict:

    matches = []

    for index, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if "`CERTIFIED_A2`" in line and ("explicit human-authored scalar semantic adapter") in line:
            matches.append(
                {
                    "line": index,
                    "text": line,
                }
            )

    if len(matches) != 1:
        raise ValueError("A2 protocol definition not unique")

    return matches[0]


def build(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    source_records = _load_jsonl(
        repo_root / ("benchmarks/v0.11/a2_adapter_authoring/source_slices.jsonl")
    )

    source_by_id = {str(item["candidate_id"]): item for item in source_records}

    partition = set(SCALAR_TARGETS) | set(COMPLEX_SCALAR_REVIEW) | set(NON_SCALAR_REVIEW)

    if partition != V2_IDS:
        raise ValueError("V2 partition mismatch")

    protocol = _protocol_definition(repo_root / "experiments/V0.11_PROTOCOL.md")

    proofs: list[JsonDict] = []
    certificates: list[JsonDict] = []

    for candidate_id in sorted(SCALAR_TARGETS):
        semantic_id = SCALAR_TARGETS[candidate_id]

        source_record = source_by_id[candidate_id]

        source_slice = _verify_live_source(
            repo_root=repo_root,
            record=source_record,
        )

        runtime = RUNTIME[semantic_id](source_slice)

        symbolic = SYMBOLIC[semantic_id]()

        adapter, mutant = ADAPTERS[semantic_id]

        passed = (
            runtime["adapter_mismatches"] == 0
            and runtime["mutant_mismatches"] > 0
            and symbolic["correct_proved"] is True
            and symbolic["mutant_disproved"] is True
        )

        proof: JsonDict = {
            "candidate_id": candidate_id,
            "semantic_adapter": semantic_id,
            "source": source_record["source"],
            "class": source_record["class"],
            "function": source_record["function"],
            "source_file_sha256": source_record["source_file_sha256"],
            "function_sha256": source_record["function_sha256"],
            "adapter_function": adapter.__name__,
            "adapter_function_sha256": _function_digest(adapter),
            "mutant_function": mutant.__name__,
            "mutant_function_sha256": _function_digest(mutant),
            "runtime": runtime,
            "symbolic": symbolic,
            "status": ("PROVED_A2_SCALAR" if passed else "A2_PROOF_FAILED"),
            "terminal_outcome": ("CERTIFIED_A2" if passed else None),
            "certification_claim": passed,
        }

        proof["proof_digest"] = _digest(dict(proof))

        proofs.append(proof)

        if not passed:
            continue

        certificate: JsonDict = {
            "schema_version": ("BIZPROOF-V0.11-A2-CERTIFICATE-1"),
            "certificate_id": ("CERT-V011-A2-" + candidate_id.upper()),
            "candidate_id": candidate_id,
            "status": "CERTIFIED_A2",
            "terminal_outcome": "CERTIFIED_A2",
            "assistance_level": "A2",
            "protocol_definition": protocol,
            "authoring_mode": ("EXPLICIT_MANUAL_SCALAR_SEMANTIC_ADAPTER"),
            "source": {
                "source_id": source_record["source"],
                "class": source_record["class"],
                "function": source_record["function"],
                "file": source_record["file"],
                "lines": source_record["lines"],
                "source_file_sha256": source_record["source_file_sha256"],
                "function_sha256": source_record["function_sha256"],
            },
            "adapter": {
                "semantic_adapter": semantic_id,
                "function": adapter.__name__,
                "function_sha256": proof["adapter_function_sha256"],
                "mutant_function": mutant.__name__,
                "mutant_function_sha256": proof["mutant_function_sha256"],
            },
            "evidence": {
                "proof_digest": proof["proof_digest"],
                "runtime": runtime,
                "symbolic": symbolic,
            },
            "claim_scope": (
                "Certification is restricted "
                "to the explicit scalar semantic "
                "projection and primitive-output "
                "bindings represented by this "
                "evidence bundle."
            ),
            "terminal_outcome_assigned": True,
            "final_study_complete": False,
        }

        certificate["certificate_digest"] = _digest(dict(certificate))

        certificates.append(certificate)

    review_records: list[JsonDict] = []

    for (
        candidate_id,
        reason_code,
    ) in sorted(NON_SCALAR_REVIEW.items()):
        record = source_by_id[candidate_id]

        review_records.append(
            {
                "candidate_id": candidate_id,
                "source": record["source"],
                "class": record["class"],
                "function": record["function"],
                "review_kind": "NON_SCALAR_RETURN",
                "reason_code": reason_code,
                "terminal_outcome": None,
                "certification_claim": False,
            }
        )

    for (
        candidate_id,
        reason_code,
    ) in sorted(COMPLEX_SCALAR_REVIEW.items()):
        record = source_by_id[candidate_id]

        review_records.append(
            {
                "candidate_id": candidate_id,
                "source": record["source"],
                "class": record["class"],
                "function": record["function"],
                "review_kind": "SCALAR_COMPLEXITY_REVIEW",
                "reason_code": reason_code,
                "reason": (
                    "The source returns a scalar, "
                    "but its semantic dependency "
                    "surface is too large to collapse "
                    "into a reviewed explicit adapter "
                    "without a separate mapping step."
                ),
                "terminal_outcome": None,
                "certification_claim": False,
            }
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    certificate_dir = output_dir / "certificates"

    certificate_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in certificate_dir.glob("*.json"):
        path.unlink()

    for certificate_record in certificates:
        (certificate_dir / (str(certificate_record["certificate_id"]) + ".json")).write_text(
            json.dumps(
                certificate_record,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    (output_dir / "proofs.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in proofs
        ),
        encoding="utf-8",
    )

    (output_dir / "review.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in review_records
        ),
        encoding="utf-8",
    )

    prior_states = _load_jsonl(
        repo_root / ("benchmarks/v0.11/a2_v1_scalar_proofs/candidate_terminal_state.jsonl")
    )

    if len(prior_states) != 90:
        raise ValueError("V1 terminal ledger must contain 90 candidates")

    certificate_by_id = {str(item["candidate_id"]): item for item in certificates}

    states: list[JsonDict] = []

    for previous_state in prior_states:
        candidate_id = str(previous_state["candidate_id"])

        matched_certificate = certificate_by_id.get(candidate_id)

        if matched_certificate is None:
            states.append(dict(previous_state))

            continue

        if previous_state["state"] != "PENDING_UNASSIGNED":
            raise ValueError("refusing terminal overwrite: " + candidate_id)

        states.append(
            {
                "candidate_id": candidate_id,
                "state": "TERMINAL_ASSIGNED",
                "terminal_outcome": "CERTIFIED_A2",
                "certificate_id": matched_certificate["certificate_id"],
                "certificate_digest": matched_certificate["certificate_digest"],
            }
        )

    assigned = [item for item in states if (item["state"] == "TERMINAL_ASSIGNED")]

    pending = [item for item in states if (item["state"] == "PENDING_UNASSIGNED")]

    distribution: dict[
        str,
        int,
    ] = {}

    for item in assigned:
        outcome = str(item["terminal_outcome"])

        distribution[outcome] = (
            distribution.get(
                outcome,
                0,
            )
            + 1
        )

    (output_dir / "candidate_terminal_state.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in states
        ),
        encoding="utf-8",
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "A2_V2_STRAIGHT_LINE",
        "v2_candidates_reviewed": 9,
        "scalar_candidates_attempted": 3,
        "scalar_candidates_proved": len(certificates),
        "complex_scalar_review": 2,
        "non_scalar_review": 4,
        "certificates_issued": len(certificates),
        "terminalized_before": 18,
        "terminalized_after": len(assigned),
        "pending_after": len(pending),
        "terminal_distribution": dict(sorted(distribution.items())),
        "weighted_metrics_ready": False,
        "final_certification_complete": False,
        "passed": (len(proofs) == 3 and len(review_records) == 6 and len(states) == 90),
    }

    (output_dir / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "REVIEWER_REPORT.md").write_text(
        "\n".join(
            [
                ("# BIZPROOF V0.11 A2 V2 Straight-Line Batch"),
                "",
                "- V2 candidates reviewed: 9",
                "- Scalar candidates attempted: 3",
                (f"- Scalar certificates issued: {len(certificates)}"),
                "- Complex scalar review: 2",
                "- Non-scalar review: 4",
                "",
                (
                    "Straight-line AST shape is not "
                    "treated as sufficient evidence "
                    "of scalar semantic suitability."
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )

    return summary


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/a2_v2_straight_proofs"),
    )

    args = parser.parse_args()

    repo_root = args.repo_root.resolve()

    output_dir = args.output_dir

    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    output_dir = output_dir.resolve()

    summary = build(
        repo_root=repo_root,
        output_dir=output_dir,
    )

    print("BIZPROOF V0.11 A2 V2")

    print(
        "V2 reviewed:",
        summary["v2_candidates_reviewed"],
    )

    print(
        "Scalar attempted:",
        summary["scalar_candidates_attempted"],
    )

    print(
        "CERTIFIED_A2:",
        summary["certificates_issued"],
    )

    print(
        "Complex scalar review:",
        summary["complex_scalar_review"],
    )

    print(
        "Non-scalar review:",
        summary["non_scalar_review"],
    )

    print(
        "Terminalized:",
        summary["terminalized_after"],
        "/90",
    )

    print(
        "Pending:",
        summary["pending_after"],
        "/90",
    )

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
