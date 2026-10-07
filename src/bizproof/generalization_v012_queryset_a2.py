"""V0.12 declarative query-plan semantic projection."""

from __future__ import annotations

import json
from dataclasses import dataclass

from bizproof.semantic_values_v012 import SemanticReference


@dataclass(frozen=True, slots=True)
class QueryPredicate:
    """A declarative equality predicate over a typed reference."""

    field: str
    value: SemanticReference


@dataclass(frozen=True, slots=True)
class SemanticQueryPlan:
    """Framework-independent lazy relational query description."""

    source: SemanticReference
    predicates: tuple[QueryPredicate, ...]


@dataclass(frozen=True, slots=True)
class QuerySource:
    """Abstract QuerySet-producing relation with stable identity."""

    identity: int

    def filter(
        self,
        *,
        subevent: SemanticReference,
    ) -> SemanticQueryPlan:
        return SemanticQueryPlan(
            source=SemanticReference(
                type_name="QuotaRelation",
                identity=self.identity,
            ),
            predicates=(
                QueryPredicate(
                    field="subevent",
                    value=subevent,
                ),
            ),
        )


def raw_quotas_query(
    variation_is_none: bool,
    item_quotas: QuerySource,
    variation_quotas: QuerySource,
    subevent: SemanticReference,
) -> SemanticQueryPlan:
    return (
        item_quotas.filter(subevent=subevent)
        if variation_is_none
        else variation_quotas.filter(subevent=subevent)
    )


def adapt_quotas_query(
    variation_is_none: bool,
    item_quotas_source_id: int,
    variation_quotas_source_id: int,
    subevent_id: int,
) -> SemanticQueryPlan:
    return raw_quotas_query(
        variation_is_none,
        QuerySource(item_quotas_source_id),
        QuerySource(variation_quotas_source_id),
        SemanticReference(
            type_name="Subevent",
            identity=subevent_id,
        ),
    )


def mutant_quotas_query(
    variation_is_none: bool,
    item_quotas_source_id: int,
    variation_quotas_source_id: int,
    subevent_id: int,
) -> SemanticQueryPlan:
    item_quotas = QuerySource(item_quotas_source_id)

    variation_quotas = QuerySource(variation_quotas_source_id)

    subevent = SemanticReference(
        type_name="Subevent",
        identity=subevent_id,
    )

    return (
        variation_quotas.filter(subevent=subevent)
        if variation_is_none
        else item_quotas.filter(subevent=subevent)
    )


def query_plan_fingerprint(
    plan: SemanticQueryPlan,
) -> str:
    payload = {
        "kind": "QUERY_PLAN",
        "source": {
            "type_name": plan.source.type_name,
            "identity": plan.source.identity,
        },
        "predicates": [
            {
                "field": predicate.field,
                "value": {
                    "type_name": predicate.value.type_name,
                    "identity": predicate.value.identity,
                },
            }
            for predicate in plan.predicates
        ],
    }

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )
