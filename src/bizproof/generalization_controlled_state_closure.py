from __future__ import annotations

import argparse
import ast
import hashlib
import json
import textwrap
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

JsonDict = dict[str, Any]


TARGETS: dict[str, JsonDict] = {
    "2309036b0c69ad48": {
        "source": "django_oscar",
        "file": "src/oscar/apps/basket/forms.py",
        "class": "AddToBasketForm",
        "function": "_add_option_field",
        "lines": [278, 288],
        "function_sha256": "eddb810f17547f52e721d8014ab13075b4e1d1e919384c096157e1e7d299d94a",
        "reason_code": "FORM_STATE_MUTATION_OUTSIDE_FORMAL_SUBSET",
    },
    "4b57e2d73c695a41": {
        "source": "django_oscar",
        "file": "src/oscar/apps/basket/abstract_models.py",
        "class": "AbstractBasket",
        "function": "thaw",
        "lines": [391, 396],
        "function_sha256": "04d0c6d989e859716852320a74d4cdc881f86e1c70aba60820dc4919985dad2d",
        "reason_code": "OBJECT_STATE_TRANSITION_OUTSIDE_FORMAL_SUBSET",
    },
    "7cf281a33e5781df": {
        "source": "pretix",
        "file": "src/pretix/base/models/orders.py",
        "class": "OrderFee",
        "function": "price",
        "lines": [2511, 2512],
        "function_sha256": "f0accaef8a5a1f74d9bcbbc75d868c2ad7b73bc1d32095a5080e5e6fd195563f",
        "reason_code": "OBJECT_STATE_TRANSITION_OUTSIDE_FORMAL_SUBSET",
    },
    "8048a564541f5408": {
        "source": "pretix",
        "file": "src/pretix/base/services/orders.py",
        "class": "OrderChangeManager",
        "function": "regenerate_secret",
        "lines": [1809, 1810],
        "function_sha256": "d16fad3b28669e38484c20256968af8c36ae2b57f9bd09b78f618347570d6173",
        "reason_code": "OPERATION_LIST_MUTATION_OUTSIDE_FORMAL_SUBSET",
    },
    "91b2dc32504282fc": {
        "source": "django_oscar",
        "file": "src/oscar/apps/basket/utils.py",
        "class": "LineDiscountRegistry",
        "function": "discount",
        "lines": [215, 221],
        "function_sha256": "013e10398bd80cee91264ec81f916c01eea7ce95585b475196f7f2fae88dc475",
        "reason_code": "MULTI_STATE_MUTATION_OUTSIDE_FORMAL_SUBSET",
    },
    "b2996c3dd81aca55": {
        "source": "pretix",
        "file": "src/pretix/base/services/cart.py",
        "class": None,
        "function": "add_payment_to_cart_session",
        "lines": [1588, 1608],
        "function_sha256": "17b1c4649a6abb9206960628c4668dfec2b0607265f0e2752991f33d66720b04",
        "reason_code": "SESSION_STATE_MUTATION_OUTSIDE_FORMAL_SUBSET",
    },
    "d7f578c3a5f20b8a": {
        "source": "pretix",
        "file": "src/pretix/base/services/orders.py",
        "class": "OrderChangeManager",
        "function": "change_fee",
        "lines": [1898, 1903],
        "function_sha256": "1fe1783cc607250e8b4e239f14bf18597d16a99fcb0e516bd623723a93a4f715",
        "reason_code": "MULTI_OBJECT_STATE_TRANSITION_OUTSIDE_FORMAL_SUBSET",
    },
    "eb12d3a44210a486": {
        "source": "pretix",
        "file": "src/pretix/base/models/orders.py",
        "class": "OrderPosition",
        "function": "checkin_texts",
        "lines": [2676, 2684],
        "function_sha256": "c0940eb57388bf8cbbaabf04499486b19128fed8e38e5667b6dd5c794fab29ab",
        "reason_code": "NONSCALAR_LIST_SEMANTICS_OUTSIDE_FORMAL_SUBSET",
    },
}


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
    ).hexdigest()


def _load_jsonl(path: Path) -> list[JsonDict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _locked_source(
    repo_root: Path,
    manifest: JsonDict,
) -> tuple[str, str]:
    path = repo_root / "external_sources/v0.6" / str(manifest["source"]) / str(manifest["file"])

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    tree = ast.parse(source)
    start, end = manifest["lines"]

    nodes = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == manifest["function"]
            and node.lineno >= start
            and node.lineno <= end
        )
    ]

    if len(nodes) != 1:
        raise ValueError(f"{manifest['function']}: expected one function, got {len(nodes)}")

    segment = ast.get_source_segment(
        source,
        nodes[0],
    )

    if segment is None:
        raise ValueError("unable to recover source slice")

    digest = hashlib.sha256(segment.encode("utf-8")).hexdigest()

    if digest != manifest["function_sha256"]:
        raise ValueError("locked function SHA mismatch: " + str(manifest["function"]))

    return segment, digest


def _compile(
    source_slice: str,
    function_name: str,
    extra: dict[str, Any] | None = None,
) -> Callable[..., Any]:
    namespace: dict[str, Any] = {
        "Decimal": Decimal,
    }

    if extra:
        namespace.update(extra)

    exec(
        compile(
            textwrap.dedent(source_slice),
            "<w7-locked-source>",
            "exec",
        ),
        namespace,
    )

    result = namespace[function_name]

    if not callable(result):
        raise ValueError("compiled object is not callable")

    return cast(Callable[..., Any], result)


def _run_option_field(source: str) -> JsonDict:
    def default_factory(
        form: Any,
        product: Any,
        option: Any,
    ) -> tuple[str, Any]:
        del form, product
        return ("DEFAULT", option.code)

    function = _compile(
        source,
        "_add_option_field",
        {"_option_text_field": default_factory},
    )

    passed = True

    for option_type, expected in (
        ("choice", "CHOICE"),
        ("unknown", "DEFAULT"),
    ):
        obj = SimpleNamespace(
            fields={},
            OPTION_FIELD_FACTORIES={
                "choice": (lambda form, product, option: ("CHOICE", option.code))
            },
        )

        option = SimpleNamespace(
            type=option_type,
            code="size",
        )

        function(
            obj,
            object(),
            option,
        )

        passed &= obj.fields["size"][0] == expected

    return {
        "cases": 2,
        "passed": bool(passed),
    }


def _run_thaw(source: str) -> JsonDict:
    function = _compile(
        source,
        "thaw",
    )

    class Basket:
        OPEN = "OPEN"

        def __init__(self) -> None:
            self.status = "FROZEN"
            self.save_calls = 0

        def save(self) -> None:
            self.save_calls += 1

    obj = Basket()
    result = function(obj)

    return {
        "cases": 1,
        "passed": bool(result is None and obj.status == "OPEN" and obj.save_calls == 1),
    }


def _run_price(source: str) -> JsonDict:
    function = _compile(
        source,
        "price",
    )

    values = [
        Decimal("0"),
        Decimal("4.50"),
        Decimal("-2"),
    ]

    passed = True

    for value in values:
        obj = SimpleNamespace(value=Decimal("99"))

        result = function(
            obj,
            value,
        )

        passed &= result is None and obj.value == value

    return {
        "cases": len(values),
        "passed": bool(passed),
    }


def _run_regenerate(source: str) -> JsonDict:
    class OrderPosition:
        pass

    function = _compile(
        source,
        "regenerate_secret",
        {"OrderPosition": OrderPosition},
    )

    class Manager:
        def __init__(self) -> None:
            self._operations: list[Any] = []

        @staticmethod
        def RegenerateSecretOperation(
            position: Any,
        ) -> tuple[str, Any]:
            return ("REGENERATE", position)

    obj = Manager()
    position = OrderPosition()

    result = function(
        obj,
        position,
    )

    return {
        "cases": 1,
        "passed": bool(result is None and obj._operations == [("REGENERATE", position)]),
    }


def _run_discount(source: str) -> JsonDict:
    class DiscountApplication:
        def __init__(
            self,
            amount: Any,
            quantity: Any,
            incl_tax: Any,
            offer: Any,
        ) -> None:
            self.amount = amount
            self.quantity = quantity
            self.incl_tax = incl_tax
            self.offer = offer

    function = _compile(
        source,
        "discount",
        {
            "DiscountApplication": DiscountApplication,
        },
    )

    class Registry:
        def __init__(self) -> None:
            self._discounts: list[Any] = []
            self._discount_incl_tax = Decimal("1")
            self._discount_excl_tax = Decimal("1")
            self.consume_calls: list[Any] = []

        def consume(
            self,
            quantity: Any,
            *,
            offer: Any = None,
        ) -> None:
            self.consume_calls.append((quantity, offer))

    passed = True

    for incl_tax in (
        True,
        False,
    ):
        obj = Registry()

        result = function(
            obj,
            Decimal("2.5"),
            3,
            incl_tax,
            "OFFER",
        )

        passed &= (
            result is None and len(obj._discounts) == 1 and obj.consume_calls == [(3, "OFFER")]
        )

        if incl_tax:
            passed &= obj._discount_incl_tax is None
        else:
            passed &= obj._discount_excl_tax is None

    return {
        "cases": 2,
        "passed": bool(passed),
    }


def _run_cart(source: str) -> JsonDict:
    class UUIDStub:
        counter = 0

        @classmethod
        def uuid4(cls) -> str:
            cls.counter += 1
            return f"UUID-{cls.counter}"

    function = _compile(
        source,
        "add_payment_to_cart_session",
        {"uuid": UUIDStub},
    )

    provider = SimpleNamespace(
        identifier="demo",
        multi_use_supported=True,
    )

    session: dict[str, Any] = {}

    result = function(
        session,
        provider,
        Decimal("1"),
        Decimal("10"),
        {"x": 1},
    )

    payment = session["payments"][0]

    return {
        "cases": 1,
        "passed": bool(
            result is None
            and payment["provider"] == "demo"
            and payment["multi_use_supported"] is True
            and payment["min_value"] == "1"
            and payment["max_value"] == "10"
            and session["payments_postpone"] is False
        ),
    }


def _run_change_fee(source: str) -> JsonDict:
    class OrderFee:
        pass

    class Taxed:
        def __init__(
            self,
            gross: Decimal,
        ) -> None:
            self.gross = gross

    class Rule:
        def __init__(
            self,
            increment: Decimal,
        ) -> None:
            self.increment = increment

        def tax(
            self,
            value: Decimal,
            **kwargs: Any,
        ) -> Taxed:
            del kwargs
            return Taxed(value + self.increment)

    class TaxRule:
        @staticmethod
        def zero() -> Rule:
            return Rule(Decimal("0"))

    function = _compile(
        source,
        "change_fee",
        {
            "OrderFee": OrderFee,
            "TaxRule": TaxRule,
        },
    )

    class Manager:
        def __init__(self) -> None:
            self._invoice_address = "ADDRESS"
            self._totaldiff_guesstimate = Decimal("0")
            self._invoice_dirty = False
            self._operations: list[Any] = []

        @staticmethod
        def FeeValueOperation(
            fee: Any,
            value: Any,
            diff: Any,
        ) -> tuple[Any, Any, Any]:
            return (fee, value, diff)

    passed = True

    for rule, gross in (
        (None, Decimal("10")),
        (Rule(Decimal("2")), Decimal("12")),
    ):
        fee = SimpleNamespace(
            tax_rule=rule,
            value=Decimal("4"),
        )

        obj = Manager()

        result = function(
            obj,
            fee,
            Decimal("10"),
        )

        diff = gross - Decimal("4")

        passed &= (
            result is None
            and obj._invoice_dirty is True
            and obj._totaldiff_guesstimate == diff
            and len(obj._operations) == 1
            and obj._operations[0][2] == diff
        )

    return {
        "cases": 2,
        "passed": bool(passed),
    }


def _run_checkin(source: str) -> JsonDict:
    function = _compile(
        source,
        "checkin_texts",
    )

    cases = [
        (
            "",
            False,
            "",
            "",
            [],
        ),
        (
            "ORDER",
            False,
            "",
            "",
            ["ORDER"],
        ),
        (
            "ORDER",
            True,
            "VAR",
            "ITEM",
            ["ORDER", "VAR", "ITEM"],
        ),
        (
            "",
            True,
            "",
            "ITEM",
            ["ITEM"],
        ),
    ]

    passed = True

    for (
        order_text,
        variation_id,
        variation_text,
        item_text,
        expected,
    ) in cases:
        obj = SimpleNamespace(
            order=SimpleNamespace(
                checkin_text=order_text,
            ),
            variation_id=variation_id,
            variation=SimpleNamespace(
                checkin_text=variation_text,
            ),
            item=SimpleNamespace(
                checkin_text=item_text,
            ),
        )

        passed &= function(obj) == expected

    return {
        "cases": len(cases),
        "passed": bool(passed),
    }


RUNNERS: dict[
    str,
    Callable[[str], JsonDict],
] = {
    "2309036b0c69ad48": _run_option_field,
    "4b57e2d73c695a41": _run_thaw,
    "7cf281a33e5781df": _run_price,
    "8048a564541f5408": _run_regenerate,
    "91b2dc32504282fc": _run_discount,
    "b2996c3dd81aca55": _run_cart,
    "d7f578c3a5f20b8a": _run_change_fee,
    "eb12d3a44210a486": _run_checkin,
}


def build(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:
    if len(TARGETS) != 8 or set(TARGETS) != set(RUNNERS):
        raise ValueError("invalid W7 target set")

    prior = _load_jsonl(
        repo_root
        / "benchmarks/v0.11/"
        / "residual_binding_closure/"
        / "candidate_terminal_state.jsonl"
    )

    if len(prior) != 90:
        raise ValueError("expected 90 ledger rows")

    prior_by_id = {str(row["candidate_id"]): row for row in prior}

    for candidate_id in TARGETS:
        if prior_by_id[candidate_id]["state"] != "PENDING_UNASSIGNED":
            raise ValueError("target no longer pending: " + candidate_id)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    evidence_dir = output_dir / "negative_evidence"

    evidence_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    executions: list[JsonDict] = []
    negatives: list[JsonDict] = []

    for candidate_id in sorted(TARGETS):
        manifest = TARGETS[candidate_id]

        source_slice, function_sha = _locked_source(
            repo_root,
            manifest,
        )

        execution = RUNNERS[candidate_id](source_slice)

        if execution["passed"] is not True:
            raise ValueError("controlled execution failed: " + candidate_id)

        execution_record: JsonDict = {
            "candidate_id": candidate_id,
            "source": manifest["source"],
            "class": manifest["class"],
            "function": manifest["function"],
            "function_sha256": function_sha,
            "status": "CONTROLLED_EXECUTION_ESTABLISHED",
            "cases": execution["cases"],
            "passed": True,
            "sandbox": "DETERMINISTIC_LOCAL_STUBS",
            "certification_claim": False,
        }

        execution_record["execution_evidence_digest"] = _digest(dict(execution_record))

        executions.append(execution_record)

        negative: JsonDict = {
            "schema_version": "BIZPROOF-V0.11-NEGATIVE-EVIDENCE-1",
            "candidate_id": candidate_id,
            "terminal_outcome": "NOT_CERTIFIED_UNSUPPORTED",
            "reason_code": manifest["reason_code"],
            "reason": (
                "Controlled execution of the "
                "locked source slice is established, "
                "but its observable semantics require "
                "state transition, collection mutation "
                "or non-scalar output semantics outside "
                "the frozen V0.11 formal certification "
                "subset."
            ),
            "controlled_execution_status": "ESTABLISHED",
            "execution_evidence_digest": execution_record["execution_evidence_digest"],
            "interpretation": (
                "This is not an execution failure. "
                "The candidate executes successfully "
                "under controlled deterministic stubs; "
                "formal certification is withheld "
                "because the required semantics exceed "
                "the frozen supported subset."
            ),
            "source": {
                "source_id": manifest["source"],
                "class": manifest["class"],
                "function": manifest["function"],
                "file": manifest["file"],
                "function_sha256": function_sha,
            },
            "certification_claim": False,
        }

        negative["negative_evidence_digest"] = _digest(dict(negative))

        negatives.append(negative)

        (evidence_dir / f"{candidate_id}.json").write_text(
            json.dumps(
                negative,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    negative_by_id = {row["candidate_id"]: row for row in negatives}

    states: list[JsonDict] = []

    for previous in prior:
        candidate_id = str(previous["candidate_id"])

        matched = negative_by_id.get(candidate_id)

        if matched is None:
            states.append(dict(previous))
            continue

        states.append(
            {
                "candidate_id": candidate_id,
                "state": "TERMINAL_ASSIGNED",
                "terminal_outcome": "NOT_CERTIFIED_UNSUPPORTED",
                "negative_evidence_digest": matched["negative_evidence_digest"],
                "execution_evidence_digest": matched["execution_evidence_digest"],
            }
        )

    assigned = [row for row in states if row["state"] == "TERMINAL_ASSIGNED"]

    pending = [row for row in states if row["state"] == "PENDING_UNASSIGNED"]

    (output_dir / "execution_evidence.jsonl").write_text(
        "".join(
            json.dumps(
                row,
                sort_keys=True,
            )
            + "\n"
            for row in executions
        ),
        encoding="utf-8",
    )

    (output_dir / "negative_outcomes.jsonl").write_text(
        "".join(
            json.dumps(
                row,
                sort_keys=True,
            )
            + "\n"
            for row in negatives
        ),
        encoding="utf-8",
    )

    (output_dir / "candidate_terminal_state.jsonl").write_text(
        "".join(
            json.dumps(
                row,
                sort_keys=True,
            )
            + "\n"
            for row in states
        ),
        encoding="utf-8",
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "CONTROLLED_STATE_EXECUTION_CLOSURE",
        "candidates_reviewed": 8,
        "controlled_execution_established": 8,
        "not_certified_execution": 0,
        "not_certified_unsupported": 8,
        "terminalized_before": 69,
        "terminalized_after": len(assigned),
        "pending_after": len(pending),
        "final_certification_complete": False,
        "weighted_metrics_ready": False,
        "passed": (
            len(executions) == 8
            and len(negatives) == 8
            and len(states) == 90
            and len(assigned) == 77
            and len(pending) == 13
        ),
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
                "# BIZPROOF V0.11 Controlled State Execution Closure",
                "",
                "- Candidates reviewed: 8",
                "- Controlled execution established: 8",
                "- NOT_CERTIFIED_EXECUTION: 0",
                "- NOT_CERTIFIED_UNSUPPORTED: 8",
                "",
                (
                    "All eight locked source slices execute "
                    "successfully under deterministic local stubs."
                ),
                "",
                (
                    "They remain uncertified because their "
                    "observable contracts require mutable-state "
                    "or non-scalar semantics outside the frozen "
                    "V0.11 formal subset."
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
        default=Path("benchmarks/v0.11/controlled_state_closure"),
    )

    args = parser.parse_args()

    repo_root = args.repo_root.resolve()

    output_dir = args.output_dir

    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    summary = build(
        repo_root=repo_root,
        output_dir=output_dir.resolve(),
    )

    print("BIZPROOF V0.11 W7")
    print(
        "Controlled execution:",
        summary["controlled_execution_established"],
    )
    print(
        "NOT_CERTIFIED_EXECUTION:",
        summary["not_certified_execution"],
    )
    print(
        "NOT_CERTIFIED_UNSUPPORTED:",
        summary["not_certified_unsupported"],
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
