from __future__ import annotations

import argparse
import hashlib
import inspect
import itertools
import json
import textwrap
from decimal import Decimal
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

PermissionName: TypeAlias = str | tuple[str, ...] | list[str] | None


V3_IDS = {
    "8b98d0147c79c3fc",
    "4008a63ee1ef3b44",
    "41ae4a7df4780001",
    "7f523a5041034306",
    "2906fe3983a1ebe4",
    "0f73ae8d15cf3408",
    "8b3e90ca7b531556",
    "e8850260c2763222",
    "1311d905af0ebcb5",
    "674ea6fd35fa6c39",
    "f3ebe6cce422947e",
    "801278c4d91c2185",
    "7013ce92618a1e33",
}


SCALAR_TARGETS = {
    "8b98d0147c79c3fc": "COMPLETED_PAYMENT_SUM",
    "4008a63ee1ef3b44": "EVENT_PERMISSION",
    "41ae4a7df4780001": "PENDING_ORDER_SUM",
    "7f523a5041034306": "PRODUCT_QUANTITY",
    "2906fe3983a1ebe4": "NET_STOCK_LEVEL",
}


REVIEW_TARGETS = {
    "0f73ae8d15cf3408": (
        "REFERENCE_DATE_OR_NONE",
        "The result is a date/reference value or None, not a scalar business quantity.",
    ),
    "8b3e90ca7b531556": (
        "DOMAIN_PRICING_OBJECT",
        "The function returns pricing-domain objects "
        "whose complete observable semantics are not scalar.",
    ),
    "e8850260c2763222": (
        "DOMAIN_DISCOUNT_OBJECT_AND_SIDE_EFFECTS",
        "The function combines domain-object returns with discount and consumption side effects.",
    ),
    "1311d905af0ebcb5": (
        "SIDE_EFFECT_ONLY_REDIS_CACHE",
        "The function has no semantic return value and performs Redis/cache side effects.",
    ),
    "674ea6fd35fa6c39": (
        "INITIALIZER_SIDE_EFFECT",
        "The function is an initializer with state mutation and no scalar return contract.",
    ),
    "f3ebe6cce422947e": (
        "BOOLEAN_MESSAGE_TUPLE",
        "The externally observable result is a tuple "
        "containing both decision and human-readable reason.",
    ),
    "801278c4d91c2185": (
        "TEXTUAL_REPRESENTATION",
        "The function constructs a localized textual "
        "representation rather than a scalar business value.",
    ),
    "7013ce92618a1e33": (
        "BOOLEAN_REASON_TUPLE",
        "The result is a multi-branch tuple containing a decision and contextual reason.",
    ),
}


BINDING_SCOPE = {
    "COMPLETED_PAYMENT_SUM": (
        "payment_sum and refund_sum are the scalar aggregate "
        "outputs of the locked source queries; missing aggregate "
        "values bind to Decimal zero exactly as in the source."
    ),
    "PENDING_ORDER_SUM": (
        "total, canceled status, payment_sum and refund_sum "
        "are explicit scalar bindings of the corresponding "
        "locked source fields and aggregate outputs."
    ),
    "PRODUCT_QUANTITY": (
        "basket persistence is represented by id presence and "
        "quantity is the aggregate quantity__sum output; None "
        "and zero follow the source's `quantity or 0` semantics."
    ),
    "NET_STOCK_LEVEL": (
        "num_in_stock and num_allocated preserve the locked "
        "source's optional numeric-field semantics."
    ),
    "EVENT_PERMISSION": (
        "all-events access, organizer equality, event membership, "
        "permission-set membership and permission-name shape are "
        "explicit bindings of the locked source predicates."
    ),
}


def adapt_completed_payment_sum(
    payment_sum: Decimal | None,
    refund_sum: Decimal | None,
) -> Decimal:

    payment = payment_sum or Decimal("0.00")

    refund = refund_sum or Decimal("0.00")

    return payment - refund


def mutant_completed_payment_sum(
    payment_sum: Decimal | None,
    refund_sum: Decimal | None,
) -> Decimal:

    payment = payment_sum or Decimal("0.00")

    refund = refund_sum or Decimal("0.00")

    return payment + refund


def adapt_pending_order_sum(
    total: Decimal,
    canceled: bool,
    payment_sum: Decimal | None,
    refund_sum: Decimal | None,
) -> Decimal:

    effective_total = Decimal("0.00") if canceled else total

    payment = payment_sum or Decimal("0.00")

    refund = refund_sum or Decimal("0.00")

    return effective_total - payment + refund


def mutant_pending_order_sum(
    total: Decimal,
    canceled: bool,
    payment_sum: Decimal | None,
    refund_sum: Decimal | None,
) -> Decimal:

    del canceled

    payment = payment_sum or Decimal("0.00")

    refund = refund_sum or Decimal("0.00")

    return total - payment + refund


def adapt_product_quantity(
    basket_has_id: bool,
    aggregate_quantity: int | None,
) -> int:

    if not basket_has_id:
        return 0

    return aggregate_quantity or 0


def mutant_product_quantity(
    basket_has_id: bool,
    aggregate_quantity: int | None,
) -> int:

    del basket_has_id

    return aggregate_quantity or 0


def adapt_net_stock_level(
    num_in_stock: int | None,
    num_allocated: int | None,
) -> int:

    if num_in_stock is None:
        return 0

    if num_allocated is None:
        return num_in_stock

    return num_in_stock - num_allocated


def mutant_net_stock_level(
    num_in_stock: int | None,
    num_allocated: int | None,
) -> int:

    if num_in_stock is None:
        return 0

    if num_allocated is None:
        return num_in_stock

    return num_in_stock + num_allocated


def adapt_event_permission(
    all_events: bool,
    organizer_matches: bool,
    event_in_limit: bool,
    permission_set: frozenset[str],
    perm_name: PermissionName,
) -> bool:

    has_event_access = (all_events and organizer_matches) or event_in_limit

    if isinstance(
        perm_name,
        (
            tuple,
            list,
        ),
    ):
        return has_event_access and any(permission in permission_set for permission in perm_name)

    return has_event_access and (not perm_name or perm_name in permission_set)


def mutant_event_permission(
    all_events: bool,
    organizer_matches: bool,
    event_in_limit: bool,
    permission_set: frozenset[str],
    perm_name: PermissionName,
) -> bool:

    has_event_access = (all_events and organizer_matches) or event_in_limit

    if isinstance(
        perm_name,
        (
            tuple,
            list,
        ),
    ):
        return has_event_access and all(permission in permission_set for permission in perm_name)

    return has_event_access and (not perm_name or perm_name in permission_set)


ADAPTERS = {
    "COMPLETED_PAYMENT_SUM": (
        adapt_completed_payment_sum,
        mutant_completed_payment_sum,
    ),
    "PENDING_ORDER_SUM": (
        adapt_pending_order_sum,
        mutant_pending_order_sum,
    ),
    "PRODUCT_QUANTITY": (
        adapt_product_quantity,
        mutant_product_quantity,
    ),
    "NET_STOCK_LEVEL": (
        adapt_net_stock_level,
        mutant_net_stock_level,
    ),
    "EVENT_PERMISSION": (
        adapt_event_permission,
        mutant_event_permission,
    ),
}


class _AggregateQuery:
    def __init__(
        self,
        value: Any,
        key: str,
    ) -> None:

        self.value = value
        self.key = key

    def filter(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> _AggregateQuery:

        del args
        del kwargs

        return self

    def aggregate(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:

        del args
        del kwargs

        return {self.key: self.value}


class _AllCollection:
    def __init__(
        self,
        values: list[Any],
    ) -> None:

        self.values = values

    def all(
        self,
    ) -> list[Any]:

        return list(self.values)


def _sum_marker(
    value: str,
) -> str:

    return value


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


def _runtime_completed_payment(
    source_slice: str,
) -> JsonDict:

    payment_state = SimpleNamespace(
        PAYMENT_STATE_CONFIRMED="CONFIRMED",
        PAYMENT_STATE_REFUNDED="REFUNDED",
    )

    refund_state = SimpleNamespace(
        REFUND_STATE_DONE="DONE",
        REFUND_STATE_TRANSIT="TRANSIT",
    )

    function = _exec_function(
        source_slice,
        "completed_payment_sum",
        {
            "Decimal": Decimal,
            "Sum": _sum_marker,
            "OrderPayment": payment_state,
            "OrderRefund": refund_state,
        },
    )

    values: list[Decimal | None] = [
        None,
        Decimal("0.00"),
        Decimal("4.50"),
        Decimal("10.00"),
    ]

    comparisons = 0
    adapter_mismatches = 0
    mutant_mismatches = 0

    for payment_sum, refund_sum in itertools.product(
        values,
        values,
    ):
        obj = SimpleNamespace(
            order=SimpleNamespace(
                payments=_AggregateQuery(
                    payment_sum,
                    "s",
                ),
                refunds=_AggregateQuery(
                    refund_sum,
                    "s",
                ),
            )
        )

        external = function(obj)

        adapter = adapt_completed_payment_sum(
            payment_sum,
            refund_sum,
        )

        mutant = mutant_completed_payment_sum(
            payment_sum,
            refund_sum,
        )

        comparisons += 1

        if external != adapter:
            adapter_mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

    return {
        "validation_domain": ("payment/refund aggregate scalars in {None,0,4.50,10.00}"),
        "comparisons": comparisons,
        "adapter_mismatches": adapter_mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _runtime_pending_sum(
    source_slice: str,
) -> JsonDict:

    order_type = SimpleNamespace(STATUS_CANCELED="CANCELED")

    payment_state = SimpleNamespace(
        PAYMENT_STATE_CONFIRMED="CONFIRMED",
        PAYMENT_STATE_REFUNDED="REFUNDED",
    )

    refund_state = SimpleNamespace(
        REFUND_STATE_DONE="DONE",
        REFUND_STATE_TRANSIT="TRANSIT",
        REFUND_STATE_CREATED="CREATED",
    )

    function = _exec_function(
        source_slice,
        "pending_sum",
        {
            "Decimal": Decimal,
            "Sum": _sum_marker,
            "Order": order_type,
            "OrderPayment": payment_state,
            "OrderRefund": refund_state,
        },
    )

    totals = [
        Decimal("0.00"),
        Decimal("10.00"),
        Decimal("100.00"),
    ]

    aggregate_values: list[Decimal | None] = [
        None,
        Decimal("0.00"),
        Decimal("3.00"),
        Decimal("8.00"),
    ]

    comparisons = 0
    adapter_mismatches = 0
    mutant_mismatches = 0

    for (
        total,
        canceled,
        payment_sum,
        refund_sum,
    ) in itertools.product(
        totals,
        (
            False,
            True,
        ),
        aggregate_values,
        aggregate_values,
    ):
        obj = SimpleNamespace(
            total=total,
            status=("CANCELED" if canceled else "PAID"),
            payments=_AggregateQuery(
                payment_sum,
                "s",
            ),
            refunds=_AggregateQuery(
                refund_sum,
                "s",
            ),
        )

        external = function(obj)

        adapter = adapt_pending_order_sum(
            total,
            bool(canceled),
            payment_sum,
            refund_sum,
        )

        mutant = mutant_pending_order_sum(
            total,
            bool(canceled),
            payment_sum,
            refund_sum,
        )

        comparisons += 1

        if external != adapter:
            adapter_mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

    return {
        "validation_domain": (
            "bounded Decimal total/payment/refund aggregates with canceled/non-canceled status"
        ),
        "comparisons": comparisons,
        "adapter_mismatches": adapter_mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _runtime_product_quantity(
    source_slice: str,
) -> JsonDict:

    function = _exec_function(
        source_slice,
        "product_quantity",
        {
            "Sum": _sum_marker,
        },
    )

    quantities: list[int | None] = [
        None,
        0,
        1,
        2,
        7,
    ]

    comparisons = 0
    adapter_mismatches = 0
    mutant_mismatches = 0

    for (
        basket_has_id,
        quantity,
    ) in itertools.product(
        (
            False,
            True,
        ),
        quantities,
    ):
        lines = _AggregateQuery(
            quantity,
            "quantity__sum",
        )

        obj = SimpleNamespace(
            id=(1 if basket_has_id else None),
            lines=lines,
        )

        external = function(
            obj,
            object(),
        )

        adapter = adapt_product_quantity(
            bool(basket_has_id),
            quantity,
        )

        mutant = mutant_product_quantity(
            bool(basket_has_id),
            quantity,
        )

        comparisons += 1

        if external != adapter:
            adapter_mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

    return {
        "validation_domain": ("basket id present/absent and aggregate quantity in {None,0,1,2,7}"),
        "comparisons": comparisons,
        "adapter_mismatches": adapter_mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _runtime_net_stock(
    source_slice: str,
) -> JsonDict:

    function = _exec_function(
        source_slice,
        "net_stock_level",
    )

    values: list[int | None] = [
        None,
        0,
        1,
        3,
        10,
    ]

    comparisons = 0
    adapter_mismatches = 0
    mutant_mismatches = 0

    for (
        num_in_stock,
        num_allocated,
    ) in itertools.product(
        values,
        values,
    ):
        obj = SimpleNamespace(
            num_in_stock=num_in_stock,
            num_allocated=num_allocated,
        )

        external = function(obj)

        adapter = adapt_net_stock_level(
            num_in_stock,
            num_allocated,
        )

        mutant = mutant_net_stock_level(
            num_in_stock,
            num_allocated,
        )

        comparisons += 1

        if external != adapter:
            adapter_mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

    return {
        "validation_domain": ("optional stock/allocation integers in {None,0,1,3,10}"),
        "comparisons": comparisons,
        "adapter_mismatches": adapter_mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _runtime_event_permission(
    source_slice: str,
) -> JsonDict:

    function = _exec_function(
        source_slice,
        "has_event_permission",
    )

    permission_sets = [
        frozenset(),
        frozenset({"read"}),
        frozenset({"write"}),
        frozenset(
            {
                "read",
                "write",
            }
        ),
    ]

    perm_names: list[PermissionName] = [
        None,
        "",
        "read",
        "write",
        ("read",),
        ("read", "write"),
        ["read"],
        ["read", "write"],
    ]

    comparisons = 0
    adapter_mismatches = 0
    mutant_mismatches = 0

    event = "EVENT"

    for (
        all_events,
        organizer_matches,
        event_in_limit,
        permission_set,
        perm_name,
    ) in itertools.product(
        (
            False,
            True,
        ),
        (
            False,
            True,
        ),
        (
            False,
            True,
        ),
        permission_sets,
        perm_names,
    ):
        organizer = "ORG"

        supplied_organizer = "ORG" if organizer_matches else "OTHER"

        limit_values = [event] if event_in_limit else []

        obj = SimpleNamespace(
            all_events=bool(all_events),
            organizer=organizer,
            limit_events=_AllCollection(limit_values),
            _event_permission_set=(lambda permission_set=permission_set: permission_set),
        )

        external = function(
            obj,
            supplied_organizer,
            event,
            perm_name,
        )

        adapter = adapt_event_permission(
            bool(all_events),
            bool(organizer_matches),
            bool(event_in_limit),
            permission_set,
            perm_name,
        )

        mutant = mutant_event_permission(
            bool(all_events),
            bool(organizer_matches),
            bool(event_in_limit),
            permission_set,
            perm_name,
        )

        comparisons += 1

        if external != adapter:
            adapter_mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

    return {
        "validation_domain": (
            "all-events, organizer equality, event membership, "
            "four permission sets and scalar/list/tuple permission names"
        ),
        "comparisons": comparisons,
        "adapter_mismatches": adapter_mismatches,
        "mutant_mismatches": mutant_mismatches,
    }


def _solver_result(
    source: Any,
    adapter: Any,
    mutant: Any,
    constraints: list[Any] | None = None,
) -> JsonDict:

    correct = z3.Solver()

    mutant_solver = z3.Solver()

    if constraints:
        correct.add(*constraints)

        mutant_solver.add(*constraints)

    correct.add(source != adapter)

    mutant_solver.add(source != mutant)

    correct_status = correct.check()

    mutant_status = mutant_solver.check()

    return {
        "correct_solver_status": str(correct_status),
        "mutant_solver_status": str(mutant_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_disproved": mutant_status == z3.sat,
    }


def _symbolic_completed_payment() -> JsonDict:

    payment = z3.Real("payment_sum")

    refund = z3.Real("refund_sum")

    source = payment - refund

    adapter = payment - refund

    mutant = payment + refund

    result = _solver_result(
        source,
        adapter,
        mutant,
    )

    result["symbolic_domain"] = (
        "unrestricted numeric aggregate scalars after source None-to-zero binding"
    )

    return result


def _symbolic_pending_sum() -> JsonDict:

    total = z3.Real("total")

    payment = z3.Real("payment_sum")

    refund = z3.Real("refund_sum")

    canceled = z3.Bool("canceled")

    effective = z3.If(
        canceled,
        z3.RealVal(0),
        total,
    )

    source = effective - payment + refund

    adapter = effective - payment + refund

    mutant = total - payment + refund

    result = _solver_result(
        source,
        adapter,
        mutant,
    )

    result["symbolic_domain"] = "numeric totals/aggregates and boolean canceled status"

    return result


def _symbolic_product_quantity() -> JsonDict:

    basket_has_id = z3.Bool("basket_has_id")

    quantity_defined = z3.Bool("quantity_defined")

    quantity = z3.Int("quantity")

    normalized_quantity = z3.If(
        z3.And(
            quantity_defined,
            quantity != 0,
        ),
        quantity,
        0,
    )

    source = z3.If(
        basket_has_id,
        normalized_quantity,
        0,
    )

    adapter = z3.If(
        basket_has_id,
        normalized_quantity,
        0,
    )

    mutant = normalized_quantity

    result = _solver_result(
        source,
        adapter,
        mutant,
    )

    result["symbolic_domain"] = "optional integer aggregate quantity and basket-id presence"

    return result


def _symbolic_net_stock() -> JsonDict:

    stock_defined = z3.Bool("stock_defined")

    allocated_defined = z3.Bool("allocated_defined")

    stock = z3.Int("stock")

    allocated = z3.Int("allocated")

    source = z3.If(
        z3.Not(stock_defined),
        0,
        z3.If(
            z3.Not(allocated_defined),
            stock,
            stock - allocated,
        ),
    )

    adapter = z3.If(
        z3.Not(stock_defined),
        0,
        z3.If(
            z3.Not(allocated_defined),
            stock,
            stock - allocated,
        ),
    )

    mutant = z3.If(
        z3.Not(stock_defined),
        0,
        z3.If(
            z3.Not(allocated_defined),
            stock,
            stock + allocated,
        ),
    )

    result = _solver_result(
        source,
        adapter,
        mutant,
    )

    result["symbolic_domain"] = "optional integer stock/allocation fields"

    return result


def _symbolic_event_permission() -> JsonDict:

    all_events = z3.Bool("all_events")

    organizer_match = z3.Bool("organizer_match")

    event_in_limit = z3.Bool("event_in_limit")

    multi_permission = z3.Bool("multi_permission")

    scalar_permission_ok = z3.Bool("scalar_permission_ok")

    permission_1 = z3.Bool("permission_1")

    permission_2 = z3.Bool("permission_2")

    event_access = z3.Or(
        z3.And(
            all_events,
            organizer_match,
        ),
        event_in_limit,
    )

    source = z3.And(
        event_access,
        z3.If(
            multi_permission,
            z3.Or(
                permission_1,
                permission_2,
            ),
            scalar_permission_ok,
        ),
    )

    adapter = z3.And(
        event_access,
        z3.If(
            multi_permission,
            z3.Or(
                permission_1,
                permission_2,
            ),
            scalar_permission_ok,
        ),
    )

    mutant = z3.And(
        event_access,
        z3.If(
            multi_permission,
            z3.And(
                permission_1,
                permission_2,
            ),
            scalar_permission_ok,
        ),
    )

    result = _solver_result(
        source,
        adapter,
        mutant,
    )

    result["symbolic_domain"] = (
        "boolean abstraction of event access and one/two permission membership predicates"
    )

    return result


RUNTIME = {
    "COMPLETED_PAYMENT_SUM": _runtime_completed_payment,
    "PENDING_ORDER_SUM": _runtime_pending_sum,
    "PRODUCT_QUANTITY": _runtime_product_quantity,
    "NET_STOCK_LEVEL": _runtime_net_stock,
    "EVENT_PERMISSION": _runtime_event_permission,
}


SYMBOLIC = {
    "COMPLETED_PAYMENT_SUM": _symbolic_completed_payment,
    "PENDING_ORDER_SUM": _symbolic_pending_sum,
    "PRODUCT_QUANTITY": _symbolic_product_quantity,
    "NET_STOCK_LEVEL": _symbolic_net_stock,
    "EVENT_PERMISSION": _symbolic_event_permission,
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

    partition = set(SCALAR_TARGETS) | set(REVIEW_TARGETS)

    if partition != V3_IDS:
        raise ValueError("V3 candidate partition mismatch")

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
            "semantic_binding_scope": BINDING_SCOPE[semantic_id],
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
            "semantic_binding_scope": BINDING_SCOPE[semantic_id],
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
                "Certification applies only to the explicit "
                "scalar semantic projection and declared "
                "source-to-adapter bindings. It does not "
                "certify database, ORM, localization or "
                "framework behavior outside that projection."
            ),
            "terminal_outcome_assigned": True,
            "final_study_complete": False,
        }

        certificate["certificate_digest"] = _digest(dict(certificate))

        certificates.append(certificate)

    reviews: list[JsonDict] = []

    for (
        candidate_id,
        review_data,
    ) in sorted(REVIEW_TARGETS.items()):
        reason_code, reason = review_data

        record = source_by_id[candidate_id]

        reviews.append(
            {
                "candidate_id": candidate_id,
                "source": record["source"],
                "class": record["class"],
                "function": record["function"],
                "reason_code": reason_code,
                "reason": reason,
                "status": "A2_REVIEW_REQUIRED",
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
            for item in reviews
        ),
        encoding="utf-8",
    )

    prior_states = _load_jsonl(
        repo_root / ("benchmarks/v0.11/a2_v2_straight_proofs/candidate_terminal_state.jsonl")
    )

    if len(prior_states) != 90:
        raise ValueError("V2 ledger must contain 90 candidates")

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
        "phase": "A2_V3_BRANCHING",
        "v3_candidates_reviewed": 13,
        "scalar_candidates_attempted": 5,
        "scalar_candidates_proved": len(certificates),
        "review_required": 8,
        "certificates_issued": len(certificates),
        "terminalized_before": 21,
        "terminalized_after": len(assigned),
        "pending_after": len(pending),
        "terminal_distribution": dict(sorted(distribution.items())),
        "weighted_metrics_ready": False,
        "final_certification_complete": False,
        "passed": (len(proofs) == 5 and len(reviews) == 8 and len(states) == 90),
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
                ("# BIZPROOF V0.11 A2 V3 Branching Batch"),
                "",
                "- V3 candidates reviewed: 13",
                "- Scalar candidates attempted: 5",
                (f"- Scalar certificates issued: {len(certificates)}"),
                "- Review-required candidates: 8",
                "",
                (
                    "Branching syntax alone is not "
                    "treated as evidence of a certifiable "
                    "scalar semantic slice."
                ),
                "",
                (
                    "Certificates are restricted to "
                    "explicit scalar bindings and do not "
                    "claim ORM/framework equivalence."
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
        default=Path("benchmarks/v0.11/a2_v3_branching_proofs"),
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

    print("BIZPROOF V0.11 A2 V3")

    print(
        "V3 reviewed:",
        summary["v3_candidates_reviewed"],
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
        "Review required:",
        summary["review_required"],
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
