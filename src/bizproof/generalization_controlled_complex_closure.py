from __future__ import annotations

import argparse
import json
import sys
import textwrap
from collections.abc import Callable, Iterable
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

from .generalization_controlled_state_closure import (
    _compile,
    _digest,
    _load_jsonl,
    _locked_source,
)

JsonDict = dict[str, Any]


TARGETS: dict[str, JsonDict] = {
    "03e2adf4e4f323b1": {
        "source": "pretix",
        "file": "src/pretix/base/models/orders.py",
        "class": "Order",
        "function": "save",
        "lines": [584, 623],
        "function_sha256": "5bcdb7e54fd57224a99828aea6483678c29681ca486633ee10c9ec73198e4437",
        "reason_code": "MODEL_SAVE_TRANSACTION_STATE_OUTSIDE_FORMAL_SUBSET",
    },
    "1a2de6edb11465fe": {
        "source": "openfisca_france",
        "file": "openfisca_france/model/prestations/bail_reel_solidaire.py",
        "class": "bail_reel_solidaire_plafond_total",
        "function": "formula",
        "lines": [45, 69],
        "function_sha256": "27d6ae56e7604c3f313a7f4a5d86d4928004dd6ed0768fc87bf34dc449660036",
        "reason_code": "DYNAMIC_COLLECTION_SELECTION_OUTSIDE_FORMAL_SUBSET",
    },
    "3fd2d8b8a76b4834": {
        "source": "openfisca_france",
        "file": "openfisca_france/model/prestations/minima_sociaux/rsa.py",
        "class": "rsa_enfant_a_charge",
        "function": "formula_2009_06_01",
        "lines": [322, 371],
        "function_sha256": "34d5615cad6fa576eb275925c470057151eb960aa06447d4a4bdd0cca87970cb",
        "reason_code": "FAMILY_AGGREGATION_NESTED_SEMANTICS_OUTSIDE_FORMAL_SUBSET",
    },
    "63e7979762bf860b": {
        "source": "django_oscar",
        "file": "src/oscar/apps/basket/views.py",
        "class": "BasketAddView",
        "function": "form_valid",
        "lines": [359, 382],
        "function_sha256": "a9684341875d75dd6e02d83d7f404bb76640500fcea86e7e948d00ae053f4d34",
        "reason_code": "FRAMEWORK_SIGNAL_BASKET_SIDE_EFFECTS_OUTSIDE_FORMAL_SUBSET",
    },
    "7460029971aad8de": {
        "source": "pretix",
        "file": "src/pretix/base/models/items.py",
        "class": "Quota",
        "function": "availability",
        "lines": [2147, 2181],
        "function_sha256": "043e1cd9628b14e9ea89a9f905f37ce77b4b16e1c8ba9e1995ab3fb7090687ed",
        "reason_code": "SERVICE_CACHE_OBJECT_SEMANTICS_OUTSIDE_FORMAL_SUBSET",
    },
    "882c5eae0d8fd4ec": {
        "source": "pretix",
        "file": "src/pretix/base/models/orders.py",
        "class": "OrderPayment",
        "function": "create_external_refund",
        "lines": [2095, 2127],
        "function_sha256": "0c1d9b50bfa377b3f8004844ef99266333a9da475e368e05a278bae67a67e7d8",
        "reason_code": "REFUND_OBJECT_SIDE_EFFECTS_OUTSIDE_FORMAL_SUBSET",
    },
    "8a754dadf1672d0a": {
        "source": "pretix",
        "file": "src/pretix/base/models/orders.py",
        "class": "Order",
        "function": "positions_with_tickets",
        "lines": [1203, 1210],
        "function_sha256": "6333627389e891ba1a54761c7ab06169a3cd2fca9a647e81a3154760db0824f7",
        "reason_code": "PLUGIN_SIGNAL_SET_SEMANTICS_OUTSIDE_FORMAL_SUBSET",
    },
    "a79d9687185720aa": {
        "source": "django_oscar",
        "file": "src/oscar/apps/offer/abstract_models.py",
        "class": "AbstractConditionalOffer",
        "function": "save",
        "lines": [288, 296],
        "function_sha256": "7b7f79f9b3521d6f2b3b6596a97928cf35c94d12af5a0f748804edc23c8b982d",
        "reason_code": "MODEL_SAVE_STATE_TRANSITION_OUTSIDE_FORMAL_SUBSET",
    },
    "bcb091a940a8d0dd": {
        "source": "django_oscar",
        "file": "src/oscar/apps/basket/views.py",
        "class": "BasketView",
        "function": "get_formset_kwargs",
        "lines": [42, 45],
        "function_sha256": "7d84fb99ad2262850084dae8686bdb577c6ff097272a2e79ff6c0f5709646a72",
        "reason_code": "FRAMEWORK_DICT_MUTATION_OUTSIDE_FORMAL_SUBSET",
    },
}


def _compile_method(
    source_slice: str,
    *,
    function_name: str,
    base_class: type[Any],
    globals_extra: dict[str, Any] | None = None,
    package: str = "",
) -> Callable[..., Any]:

    namespace: dict[str, Any] = {
        "Base": base_class,
        "Any": Any,
        "Decimal": Decimal,
        "datetime": datetime,
        "Tuple": tuple,
        "Iterable": Iterable,
        "__name__": "bizproof_w8_sandbox",
        "__package__": package,
    }

    if globals_extra:
        namespace.update(globals_extra)

    body = textwrap.indent(
        textwrap.dedent(source_slice),
        "    ",
    )

    code = "class Candidate(Base):\n" + body + "\n"

    exec(
        compile(
            code,
            "<w8-controlled-source>",
            "exec",
        ),
        namespace,
    )

    candidate_class = namespace["Candidate"]

    result = getattr(
        candidate_class,
        function_name,
    )

    if not callable(result):
        raise ValueError("compiled method is not callable")

    return cast(
        Callable[..., Any],
        result,
    )


class _AttrDict(dict[str, Any]):
    def __getattr__(
        self,
        name: str,
    ) -> Any:

        try:
            return self[name]

        except KeyError as exc:
            raise AttributeError(name) from exc


def _select(
    conditions: list[Any],
    choices: list[Any],
) -> Any:

    for condition, choice in zip(
        conditions,
        choices,
        strict=True,
    ):
        if bool(condition):
            return choice

    return 0


def _where(
    condition: Any,
    positive: Any,
    negative: Any,
) -> Any:

    return positive if bool(condition) else negative


def _not(
    value: Any,
) -> int:

    return int(not bool(value))


def _run_bail_reel_solidaire(
    source: str,
) -> JsonDict:

    function = _compile(
        source,
        "formula",
        {
            "select": _select,
            "where": _where,
        },
    )

    def zone_parameters(
        zone: int,
    ) -> _AttrDict:

        return _AttrDict(
            {
                **{f"nb_personnes_{index}": zone * 100 + index * 10 for index in range(1, 7)},
                "nb_personnes_supplementaires": zone * 5,
            }
        )

    parameters_root = SimpleNamespace(
        prestations_sociales=SimpleNamespace(
            bail_reel_solidaire=SimpleNamespace(
                parametres_generaux=SimpleNamespace(
                    zones_abc_eligibles=[
                        1,
                        2,
                        3,
                    ],
                    nombre_personnes_maximum=6,
                ),
                plafonds_par_zones=_AttrDict(
                    {
                        "zone_1": zone_parameters(1),
                        "zone_2": zone_parameters(2),
                        "zone_3": zone_parameters(3),
                    }
                ),
            )
        )
    )

    def parameters(
        period: Any,
    ) -> Any:

        del period
        return parameters_root

    class Menage:
        def __init__(
            self,
            zone: int,
            persons: int,
        ) -> None:

            self.zone = zone
            self.persons = persons

        def __call__(
            self,
            variable: str,
            period: Any,
        ) -> int:

            del period

            if variable != "bail_reel_solidaire_zones_menage":
                raise ValueError("unexpected variable: " + variable)

            return self.zone

        def nb_persons(
            self,
        ) -> int:

            return self.persons

    cases = [
        # zone, persons, expected
        (
            1,
            1,
            110,
        ),
        (
            2,
            6,
            260,
        ),
        (
            2,
            8,
            280,
        ),
        (
            3,
            7,
            375,
        ),
    ]

    passed = True
    observed = []

    for (
        zone,
        persons,
        expected,
    ) in cases:
        result = function(
            Menage(
                zone,
                persons,
            ),
            "PERIOD",
            parameters,
        )

        observed.append(
            {
                "zone": zone,
                "persons": persons,
                "result": result,
                "expected": expected,
            }
        )

        if result != expected:
            passed = False

    return {
        "cases": len(cases),
        "passed": bool(passed),
        "observed": observed,
    }


def _run_rsa_enfant(
    source: str,
) -> JsonDict:

    function = _compile(
        source,
        "formula_2009_06_01",
        {
            "not_": _not,
            "where": _where,
        },
    )

    parameter_root = SimpleNamespace(
        prestations_sociales=SimpleNamespace(
            solidarite_insertion=SimpleNamespace(
                minima_sociaux=SimpleNamespace(
                    rsa=SimpleNamespace(
                        rsa_cond=SimpleNamespace(
                            age_pac=25,
                        ),
                        rsa_maj=SimpleNamespace(
                            majoration_isolement_en_base_rsa=SimpleNamespace(
                                femmes_enceintes=1.5,
                                par_enfant_a_charge=0.2,
                            ),
                            maj_montant_max=SimpleNamespace(
                                par_enfant_supplementaire=0.3,
                            ),
                        ),
                        rsa_m=SimpleNamespace(
                            montant_de_base_du_rsa=100,
                        ),
                    )
                )
            )
        )
    )

    def parameters(
        period: Any,
    ) -> Any:

        del period
        return parameter_root

    class Family:
        def __init__(
            self,
            *,
            enceinte: int,
            en_couple: int,
            isolement_recent: int,
            other_children_measure: int,
        ) -> None:

            self.enceinte = enceinte
            self.en_couple = en_couple
            self.isolement_recent = isolement_recent
            self.other_children_measure = other_children_measure

        def __call__(
            self,
            variable: str,
            period: Any,
        ) -> int:

            del period

            values = {
                "enceinte_fam": self.enceinte,
                "en_couple": self.en_couple,
                "rsa_isolement_recent": self.isolement_recent,
            }

            return values[variable]

        def sum(
            self,
            value: Any,
        ) -> int:

            del value

            return self.other_children_measure

    class Individu:
        def __init__(
            self,
            *,
            enfant: int,
            age: int,
            autonomie: int,
            ressources: int,
            famille: Family,
        ) -> None:

            self.values = {
                "est_enfant_dans_famille": enfant,
                "age": age,
                "autonomie_financiere": autonomie,
                "rsa_revenus_determination_enfant_a_charge": ressources,
            }

            self.famille = famille

        def __call__(
            self,
            variable: str,
            period: Any,
        ) -> int:

            del period

            return self.values[variable]

    cases: list[dict[str, Any]] = [
        # majoration applies; threshold = 70
        {
            "family": Family(
                enceinte=0,
                en_couple=0,
                isolement_recent=1,
                other_children_measure=0,
            ),
            "ressources": 50,
            "expected": 1,
        },
        {
            "family": Family(
                enceinte=0,
                en_couple=0,
                isolement_recent=1,
                other_children_measure=0,
            ),
            "ressources": 80,
            "expected": 0,
        },
        # no majoration; threshold = 30
        {
            "family": Family(
                enceinte=0,
                en_couple=1,
                isolement_recent=1,
                other_children_measure=0,
            ),
            "ressources": 20,
            "expected": 1,
        },
        {
            "family": Family(
                enceinte=0,
                en_couple=1,
                isolement_recent=1,
                other_children_measure=0,
            ),
            "ressources": 40,
            "expected": 0,
        },
        # child otherwise excluded
        {
            "family": Family(
                enceinte=0,
                en_couple=0,
                isolement_recent=1,
                other_children_measure=0,
            ),
            "ressources": 0,
            "age": 30,
            "expected": 0,
        },
    ]

    passed = True
    observed = []

    for case in cases:
        individu = Individu(
            enfant=1,
            age=int(
                case.get(
                    "age",
                    20,
                )
            ),
            autonomie=0,
            ressources=int(case["ressources"]),
            famille=cast(
                Family,
                case["family"],
            ),
        )

        result = function(
            individu,
            "PERIOD",
            parameters,
        )

        expected = int(case["expected"])

        observed.append(
            {
                "result": result,
                "expected": expected,
                "ressources": case["ressources"],
                "age": case.get(
                    "age",
                    20,
                ),
            }
        )

        if result != expected:
            passed = False

    return {
        "cases": len(cases),
        "passed": bool(passed),
        "observed": observed,
    }


W8B1_RUNNERS: dict[
    str,
    Callable[[str], JsonDict],
] = {
    "1a2de6edb11465fe": _run_bail_reel_solidaire,
    "3fd2d8b8a76b4834": _run_rsa_enfant,
}


def _run_quota_availability(
    source: str,
) -> JsonDict:

    module_names = [
        "pretix",
        "pretix.base",
        "pretix.base.services",
        "pretix.base.services.quotas",
    ]

    previous_modules = {name: sys.modules.get(name) for name in module_names}

    try:
        for name in module_names[:-1]:
            if name not in sys.modules:
                module = ModuleType(name)

                module.__path__ = []

                sys.modules[name] = module

        quota_module: Any = ModuleType("pretix.base.services.quotas")

        class QuotaAvailability:
            instances = 0

            def __init__(
                self,
                *,
                count_waitinglist: bool,
                early_out: bool,
            ) -> None:

                type(self).instances += 1

                self.count_waitinglist = count_waitinglist

                self.early_out = early_out

                self.queued: list[Any] = []

                self.results: dict[
                    Any,
                    tuple[
                        int,
                        int,
                    ],
                ] = {}

            def queue(
                self,
                quota: Any,
            ) -> None:

                self.queued.append(quota)

            def compute(
                self,
                *,
                now_dt: Any = None,
                allow_cache: bool = False,
            ) -> None:

                del now_dt
                del allow_cache

                for quota in self.queued:
                    self.results[quota] = (
                        7,
                        42,
                    )

        quota_module.QuotaAvailability = QuotaAvailability

        sys.modules["pretix.base.services.quotas"] = quota_module

        function = _compile_method(
            source,
            function_name="availability",
            base_class=object,
            package="pretix.base.models",
        )

        class Quota:
            pk: int

        quota = Quota()
        quota.pk = 10

        # Case 1: cache hit must bypass service.
        cache_hit: dict[
            Any,
            Any,
        ] = {
            10: (
                9,
                99,
            ),
            "_count_waitinglist": True,
        }

        before = QuotaAvailability.instances

        hit_result = function(
            quota,
            None,
            True,
            cache_hit,
            False,
        )

        hit_bypassed_service = QuotaAvailability.instances == before

        # Case 2: empty cache invokes service and populates cache.
        cache_compute: dict[
            Any,
            Any,
        ] = {}

        computed = function(
            quota,
            None,
            True,
            cache_compute,
            False,
        )

        compute_populated = (
            cache_compute.get(10)
            == (
                7,
                42,
            )
            and cache_compute.get("_count_waitinglist") is True
        )

        # Case 3: count_waitinglist mismatch clears stale cache.
        mismatch_cache: dict[
            Any,
            Any,
        ] = {
            10: (
                1,
                1,
            ),
            "_count_waitinglist": False,
        }

        mismatch_result = function(
            quota,
            None,
            True,
            mismatch_cache,
            False,
        )

        mismatch_recomputed = (
            mismatch_result
            == (
                7,
                42,
            )
            and mismatch_cache[10]
            == (
                7,
                42,
            )
            and mismatch_cache["_count_waitinglist"] is True
        )

        passed = (
            hit_result
            == (
                9,
                99,
            )
            and hit_bypassed_service
            and computed
            == (
                7,
                42,
            )
            and compute_populated
            and mismatch_recomputed
        )

        return {
            "cases": 3,
            "passed": bool(passed),
            "observed": {
                "cache_hit": hit_result,
                "computed": computed,
                "mismatch_recomputed": mismatch_recomputed,
                "service_instances": QuotaAvailability.instances,
            },
        }

    finally:
        for (
            name,
            previous,
        ) in previous_modules.items():
            if previous is None:
                sys.modules.pop(
                    name,
                    None,
                )

            else:
                sys.modules[name] = previous


def _run_external_refund(
    source: str,
) -> JsonDict:

    class OrderRefund:
        REFUND_STATE_EXTERNAL = "STATE_EXTERNAL"

        REFUND_SOURCE_EXTERNAL = "SOURCE_EXTERNAL"

    fixed_now = datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
    )

    function = _compile_method(
        source,
        function_name="create_external_refund",
        base_class=object,
        globals_extra={
            "OrderRefund": OrderRefund,
            "now": lambda: fixed_now,
        },
    )

    class Refund:
        def __init__(
            self,
            **kwargs: Any,
        ) -> None:

            self.__dict__.update(kwargs)

            self.local_id = 7

            self.done_calls = 0

        def done(
            self,
        ) -> None:

            self.done_calls += 1

    class RefundManager:
        def __init__(
            self,
        ) -> None:

            self.created: list[Refund] = []

        def create(
            self,
            **kwargs: Any,
        ) -> Refund:

            refund = Refund(**kwargs)

            self.created.append(refund)

            return refund

    class Order:
        def __init__(
            self,
            *,
            pending_sum: Decimal,
        ) -> None:

            self.refunds = RefundManager()

            self.pending_sum = pending_sum

            self.logs: list[
                tuple[
                    str,
                    Any,
                ]
            ] = []

        def log_action(
            self,
            action: str,
            data: Any,
        ) -> None:

            self.logs.append(
                (
                    action,
                    data,
                )
            )

    # Case 1: default full amount + default date + done()
    order1 = Order(pending_sum=Decimal("-10.00"))

    payment1 = SimpleNamespace(
        order=order1,
        amount=Decimal("10.00"),
        provider="demo",
    )

    refund1 = function(payment1)

    case1 = (
        refund1.amount == Decimal("10.00")
        and refund1.execution_date == fixed_now
        and refund1.done_calls == 1
        and len(order1.logs) == 1
    )

    # Case 2: explicit amount/date; no done().
    order2 = Order(pending_sum=Decimal("1.00"))

    payment2 = SimpleNamespace(
        order=order2,
        amount=Decimal("10.00"),
        provider="demo",
    )

    explicit_date = datetime(
        2025,
        12,
        1,
    )

    refund2 = function(
        payment2,
        Decimal("4.00"),
        explicit_date,
        '{"x": 1}',
    )

    case2 = (
        refund2.amount == Decimal("4.00")
        and refund2.execution_date == explicit_date
        and refund2.info == '{"x": 1}'
        and refund2.done_calls == 0
        and len(order2.logs) == 1
    )

    return {
        "cases": 2,
        "passed": bool(case1 and case2),
        "observed": {
            "default_amount_and_date": case1,
            "explicit_amount_and_date": case2,
        },
    }


def _run_positions_with_tickets(
    source: str,
) -> JsonDict:

    class Signal:
        def __init__(
            self,
        ) -> None:

            self.responses: list[
                tuple[
                    Any,
                    Any,
                ]
            ] = []

            self.calls = 0

        def send(
            self,
            event: Any,
            **kwargs: Any,
        ) -> list[
            tuple[
                Any,
                Any,
            ]
        ]:

            del event
            del kwargs

            self.calls += 1

            return list(self.responses)

    signal = Signal()

    function = _compile_method(
        source,
        function_name="positions_with_tickets",
        base_class=object,
        globals_extra={
            "allow_ticket_download": signal,
        },
    )

    obj = SimpleNamespace(
        event="EVENT",
        positions_with_tickets_ignoring_plugins=[
            1,
            2,
            3,
        ],
    )

    # all True -> unchanged base collection
    signal.responses = [
        (
            "plugin-a",
            True,
        ),
        (
            "plugin-b",
            True,
        ),
    ]

    all_true = function(obj)

    case1 = all_true == [
        1,
        2,
        3,
    ]

    # any False -> empty list
    signal.responses = [
        (
            "plugin-a",
            True,
        ),
        (
            "plugin-b",
            False,
        ),
    ]

    any_false = function(obj)

    case2 = any_false == []

    # iterable responses -> intersection
    signal.responses = [
        (
            "plugin-a",
            [
                1,
                2,
            ],
        ),
        (
            "plugin-b",
            {
                2,
                3,
            },
        ),
    ]

    intersection = function(obj)

    case3 = intersection == {
        2,
    }

    return {
        "cases": 3,
        "passed": bool(case1 and case2 and case3),
        "observed": {
            "all_true": all_true,
            "any_false": any_false,
            "intersection": sorted(intersection),
            "signal_calls": signal.calls,
        },
    }


W8B2_RUNNERS: dict[
    str,
    Callable[[str], JsonDict],
] = {
    "7460029971aad8de": _run_quota_availability,
    "882c5eae0d8fd4ec": _run_external_refund,
    "8a754dadf1672d0a": _run_positions_with_tickets,
}


def _compile_candidate_class(
    source_slice: str,
    *,
    base_class: type[Any],
    globals_extra: dict[str, Any] | None = None,
) -> type[Any]:

    namespace: dict[str, Any] = {
        "Base": base_class,
        "Any": Any,
        "Decimal": Decimal,
        "datetime": datetime,
        "Tuple": tuple,
        "Iterable": Iterable,
        "__name__": "bizproof_w8_candidate",
        "__package__": "",
    }

    if globals_extra:
        namespace.update(globals_extra)

    body = textwrap.indent(
        textwrap.dedent(source_slice),
        "    ",
    )

    code = "class Candidate(Base):\n" + body + "\n"

    exec(
        compile(
            code,
            "<w8-candidate-class>",
            "exec",
        ),
        namespace,
    )

    candidate = namespace["Candidate"]

    if not isinstance(
        candidate,
        type,
    ):
        raise ValueError("Candidate is not a class")

    return candidate


def _run_order_save(
    source: str,
) -> JsonDict:

    dirty_calls: list[tuple[Any, Any]] = []

    def mark_dirty(
        pk: Any,
        *,
        using: Any = None,
    ) -> None:

        dirty_calls.append(
            (
                pk,
                using,
            )
        )

    class UnsafeSave(RuntimeError):
        pass

    def fail(
        message: str,
    ) -> None:

        raise UnsafeSave(message)

    fixed_now = datetime(
        2026,
        9,
        28,
        20,
        0,
    )

    class OrderConstants:
        STATUS_PENDING = "pending"

        STATUS_PAID = "paid"

    class BaseOrder:
        def __init__(
            self,
        ) -> None:

            self.pk: Any = None

            self.code = ""

            self.datetime: Any = None

            self.expires: Any = None

            self.organizer_id: Any = None

            self.event = SimpleNamespace(organizer_id=77)

            self.status = "pending"

            self.require_approval = False

            self.deferred_fields: set[str] = set()

            self.base_save_calls: list[dict[str, Any]] = []

        def assign_code(
            self,
        ) -> None:

            self.code = "CODE-1"

        def set_expires(
            self,
        ) -> None:

            self.expires = "EXPIRES"

        def get_deferred_fields(
            self,
        ) -> set[str]:

            return set(self.deferred_fields)

        def save(
            self,
            **kwargs: Any,
        ) -> str:

            self.base_save_calls.append(dict(kwargs))

            if self.pk is None:
                self.pk = 1001

            return "BASE-SAVE"

    Candidate = _compile_candidate_class(
        source,
        base_class=BaseOrder,
        globals_extra={
            "Order": OrderConstants,
            "now": lambda: fixed_now,
            "_transactions_mark_order_dirty": mark_dirty,
            "_fail": fail,
        },
    )

    # --------------------------------------------------------
    # Case 1: new order; all missing derived fields populated.
    # --------------------------------------------------------

    dirty_calls.clear()

    first = Candidate()

    first._Candidate__initial_status_paid_or_pending = True

    result1 = first.save(using="default")

    case1 = (
        result1 == "BASE-SAVE"
        and first.code == "CODE-1"
        and first.datetime == fixed_now
        and first.expires == "EXPIRES"
        and first.organizer_id == 77
        and first.pk == 1001
        and dirty_calls
        == [
            (
                1001,
                "default",
            )
        ]
        and len(first.base_save_calls) == 1
    )

    # --------------------------------------------------------
    # Case 2: existing order changes paid/pending state.
    # --------------------------------------------------------

    dirty_calls.clear()

    second = Candidate()

    second.pk = 44
    second.code = "EXISTING"
    second.datetime = fixed_now
    second.expires = "EXISTING-EXPIRY"
    second.organizer_id = 77

    second.status = OrderConstants.STATUS_PAID

    second.require_approval = False

    second._Candidate__initial_status_paid_or_pending = False

    update_fields = {
        "status",
    }

    result2 = second.save(
        update_fields=update_fields,
        using="replica",
    )

    saved_update_fields = second.base_save_calls[0]["update_fields"]

    case2 = (
        result2 == "BASE-SAVE"
        and dirty_calls
        == [
            (
                44,
                "replica",
            )
        ]
        and {
            "status",
            "last_modified",
        }.issubset(saved_update_fields)
    )

    # --------------------------------------------------------
    # Case 3: deferred safety gate rejects unsafe save.
    # --------------------------------------------------------

    third = Candidate()

    third.pk = 55
    third.code = "EXISTING"
    third.datetime = fixed_now
    third.expires = "EXISTING-EXPIRY"
    third.organizer_id = 77

    third.deferred_fields = {
        "status",
    }

    third._Candidate__initial_status_paid_or_pending = True

    rejected = False

    try:
        third.save()

    except UnsafeSave:
        rejected = True

    case3 = rejected

    return {
        "cases": 3,
        "passed": bool(case1 and case2 and case3),
        "observed": {
            "new_order_initialization": case1,
            "dirty_transaction_detection": case2,
            "deferred_field_safety_gate": case3,
        },
    }


def _run_basket_add_view(
    source: str,
) -> JsonDict:

    message_calls: list[tuple[Any, ...]] = []

    generator_calls: list[tuple[Any, Any]] = []

    signal_calls: list[dict[str, Any]] = []

    class Messages:
        @staticmethod
        def success(
            request: Any,
            message: Any,
            *,
            extra_tags: str,
        ) -> None:

            message_calls.append(
                (
                    request,
                    message,
                    extra_tags,
                )
            )

    class BasketMessageGenerator:
        def apply_messages(
            self,
            request: Any,
            offers_before: Any,
        ) -> None:

            generator_calls.append(
                (
                    request,
                    offers_before,
                )
            )

    class Signal:
        def send(
            self,
            **kwargs: Any,
        ) -> None:

            signal_calls.append(dict(kwargs))

    class Basket:
        def __init__(
            self,
        ) -> None:

            self.add_calls: list[tuple[Any, Any, Any]] = []

        def applied_offers(
            self,
        ) -> list[str]:

            return [
                "OFFER-BEFORE",
            ]

        def add_product(
            self,
            product: Any,
            quantity: Any,
            options: Any,
        ) -> tuple[
            str,
            bool,
        ]:

            self.add_calls.append(
                (
                    product,
                    quantity,
                    options,
                )
            )

            return (
                "LINE-1",
                True,
            )

    class BaseView:
        def form_valid(
            self,
            form: Any,
        ) -> str:

            del form

            return "BASE-FORM-VALID"

        def get_success_message(
            self,
            form: Any,
        ) -> str:

            del form

            return "SUCCESS"

    Candidate = _compile_candidate_class(
        source,
        base_class=BaseView,
        globals_extra={
            "messages": Messages,
            "BasketMessageGenerator": BasketMessageGenerator,
        },
    )

    basket = Basket()

    request = SimpleNamespace(
        basket=basket,
        user="USER",
    )

    form = SimpleNamespace(
        product="PRODUCT",
        cleaned_data={"quantity": 3},
        cleaned_options=lambda: [
            "OPTION",
        ],
    )

    obj = Candidate()

    obj.request = request

    obj.add_signal = Signal()

    result = obj.form_valid(form)

    passed = (
        result == "BASE-FORM-VALID"
        and obj.line == "LINE-1"
        and obj.line_created is True
        and basket.add_calls
        == [
            (
                "PRODUCT",
                3,
                [
                    "OPTION",
                ],
            )
        ]
        and len(message_calls) == 1
        and len(generator_calls) == 1
        and len(signal_calls) == 1
        and signal_calls[0]["product"] == "PRODUCT"
    )

    return {
        "cases": 1,
        "passed": bool(passed),
        "observed": {
            "basket_add": bool(basket.add_calls),
            "message": bool(message_calls),
            "offer_message_generation": bool(generator_calls),
            "signal": bool(signal_calls),
            "super_return": result,
        },
    }


def _run_conditional_offer_save(
    source: str,
) -> JsonDict:

    class BaseOffer:
        def __init__(
            self,
        ) -> None:

            self.base_save_calls = 0

            self.is_suspended = False

            self.max_applications = 1

            self.status = "INITIAL"

            self.CONSUMED = "CONSUMED"

            self.OPEN = "OPEN"

        def get_max_applications(
            self,
        ) -> int:

            return int(self.max_applications)

        def save(
            self,
            *args: Any,
            **kwargs: Any,
        ) -> str:

            del args
            del kwargs

            self.base_save_calls += 1

            return "BASE-SAVE"

    Candidate = _compile_candidate_class(
        source,
        base_class=BaseOffer,
    )

    # zero remaining applications -> CONSUMED
    first = Candidate()

    first.max_applications = 0

    result1 = first.save()

    case1 = result1 == "BASE-SAVE" and first.status == "CONSUMED" and first.base_save_calls == 1

    # positive remaining applications -> OPEN
    second = Candidate()

    second.max_applications = 4

    result2 = second.save()

    case2 = result2 == "BASE-SAVE" and second.status == "OPEN"

    # suspended -> status untouched
    third = Candidate()

    third.is_suspended = True

    third.status = "SUSPENDED"

    result3 = third.save()

    case3 = result3 == "BASE-SAVE" and third.status == "SUSPENDED"

    return {
        "cases": 3,
        "passed": bool(case1 and case2 and case3),
        "observed": {
            "consumed": case1,
            "open": case2,
            "suspended_unchanged": case3,
        },
    }


def _run_basket_formset_kwargs(
    source: str,
) -> JsonDict:

    class BaseBasketView:
        def get_formset_kwargs(
            self,
        ) -> dict[
            str,
            Any,
        ]:

            return {"base": "VALUE"}

    Candidate = _compile_candidate_class(
        source,
        base_class=BaseBasketView,
    )

    obj = Candidate()

    obj.request = SimpleNamespace(strategy="STRATEGY")

    result = obj.get_formset_kwargs()

    passed = result == {
        "base": "VALUE",
        "strategy": "STRATEGY",
    }

    return {
        "cases": 1,
        "passed": bool(passed),
        "observed": {
            "result": result,
        },
    }


W8C_RUNNERS: dict[
    str,
    Callable[[str], JsonDict],
] = {
    "03e2adf4e4f323b1": _run_order_save,
    "63e7979762bf860b": _run_basket_add_view,
    "a79d9687185720aa": _run_conditional_offer_save,
    "bcb091a940a8d0dd": _run_basket_formset_kwargs,
}


RUNNERS: dict[
    str,
    Callable[[str], JsonDict],
] = {
    **W8B1_RUNNERS,
    **W8B2_RUNNERS,
    **W8C_RUNNERS,
}


if set(RUNNERS) != set(TARGETS):
    raise RuntimeError("W8 runner coverage mismatch")


def run_execution_probe(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    if len(TARGETS) != 9:
        raise ValueError("W8 requires exactly 9 targets")

    if set(TARGETS) != set(RUNNERS):
        raise ValueError("W8 target/runner mismatch")

    # --------------------------------------------------------
    # Lock against authoritative W7 ledger.
    # --------------------------------------------------------

    ledger_path = (
        repo_root
        / "benchmarks/v0.11/"
        / "controlled_state_closure/"
        / "candidate_terminal_state.jsonl"
    )

    ledger = _load_jsonl(ledger_path)

    if len(ledger) != 90:
        raise ValueError("expected 90 W7 ledger rows")

    terminal = [row for row in ledger if (row["state"] == "TERMINAL_ASSIGNED")]

    pending = [row for row in ledger if (row["state"] == "PENDING_UNASSIGNED")]

    if len(terminal) != 77:
        raise ValueError(f"expected 77 terminal rows before W8, got {len(terminal)}")

    if len(pending) != 13:
        raise ValueError(f"expected 13 pending rows before W8, got {len(pending)}")

    pending_ids = {str(row["candidate_id"]) for row in pending}

    missing = set(TARGETS) - pending_ids

    if missing:
        raise ValueError("W8 targets not pending: " + ", ".join(sorted(missing)))

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    records: list[JsonDict] = []

    for candidate_id in sorted(TARGETS):
        manifest = TARGETS[candidate_id]

        print()
        print("=" * 78)
        print(
            candidate_id,
            manifest["source"],
            manifest["class"],
            manifest["function"],
        )

        try:
            source_slice, digest = _locked_source(
                repo_root,
                manifest,
            )

            execution = RUNNERS[candidate_id](source_slice)

            passed = execution.get("passed") is True

            record: JsonDict = {
                "candidate_id": candidate_id,
                "source": manifest["source"],
                "class": manifest["class"],
                "function": manifest["function"],
                "function_sha256": digest,
                "execution_status": ("ESTABLISHED" if passed else "FAILED_ASSERTION"),
                "passed": passed,
                "cases": execution.get(
                    "cases",
                    0,
                ),
                "observed": execution.get(
                    "observed",
                    {},
                ),
                "terminal_outcome": None,
                "certification_claim": False,
            }

        except Exception as exc:
            record = {
                "candidate_id": candidate_id,
                "source": manifest["source"],
                "class": manifest["class"],
                "function": manifest["function"],
                "function_sha256": manifest["function_sha256"],
                "execution_status": "EXCEPTION",
                "passed": False,
                "cases": 0,
                "observed": {},
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "terminal_outcome": None,
                "certification_claim": False,
            }

        record["execution_probe_digest"] = _digest(dict(record))

        records.append(record)

        print(
            "status :",
            record["execution_status"],
        )

        print(
            "cases  :",
            record["cases"],
        )

        if record["execution_status"] == "EXCEPTION":
            print(
                "error  :",
                record["exception_type"],
                "-",
                record["exception_message"],
            )

        else:
            print(
                "passed :",
                record["passed"],
            )

    established = [row for row in records if (row["execution_status"] == "ESTABLISHED")]

    failed = [row for row in records if (row["execution_status"] != "ESTABLISHED")]

    (output_dir / "execution_probe.jsonl").write_text(
        "".join(
            json.dumps(
                row,
                sort_keys=True,
                default=str,
            )
            + "\n"
            for row in records
        ),
        encoding="utf-8",
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "COMPLEX_CONTROLLED_EXECUTION_PROBE",
        "attempted": len(records),
        "execution_established": len(established),
        "execution_not_established": len(failed),
        "terminalized_before": 77,
        "terminalized_after": 77,
        "pending_before": 13,
        "pending_after": 13,
        "terminal_outcomes_assigned": 0,
        "certification_claim": False,
        "failed_candidate_ids": [row["candidate_id"] for row in failed],
        "passed": (len(records) == 9 and len(established) == 9 and len(failed) == 0),
    }

    (output_dir / "execution_probe_summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
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
        default=Path("benchmarks/v0.11/controlled_complex_closure"),
    )

    args = parser.parse_args()

    repo_root = args.repo_root.resolve()

    output_dir = args.output_dir

    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    summary = run_execution_probe(
        repo_root=repo_root,
        output_dir=output_dir.resolve(),
    )

    print()
    print("BIZPROOF V0.11 W8 COMPLEX EXECUTION PROBE")

    print(
        "Attempted             :",
        summary["attempted"],
    )

    print(
        "Execution established :",
        summary["execution_established"],
    )

    print(
        "Execution failed      :",
        summary["execution_not_established"],
    )

    print(
        "Terminal outcomes     :",
        summary["terminal_outcomes_assigned"],
    )

    print("Ledger                : 77/90 terminal, 13 pending")

    if summary["passed"] is True:
        print("W8 EXECUTION PROBE: PASS")

        return 0

    print("W8 EXECUTION PROBE: REVIEW REQUIRED")

    print(
        "Failed candidates:",
        summary["failed_candidate_ids"],
    )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
