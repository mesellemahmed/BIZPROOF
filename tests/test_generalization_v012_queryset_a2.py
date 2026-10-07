from bizproof.generalization_v012_queryset_a2 import (
    QueryPredicate,
    QuerySource,
    SemanticQueryPlan,
    adapt_quotas_query,
    mutant_quotas_query,
    query_plan_fingerprint,
)
from bizproof.semantic_values_v012 import SemanticReference


def test_query_source_filter_is_declarative() -> None:
    source = QuerySource(identity=10)

    subevent = SemanticReference(
        type_name="Subevent",
        identity=50,
    )

    result = source.filter(subevent=subevent)

    assert result == SemanticQueryPlan(
        source=SemanticReference(
            type_name="QuotaRelation",
            identity=10,
        ),
        predicates=(
            QueryPredicate(
                field="subevent",
                value=subevent,
            ),
        ),
    )


def test_item_quota_branch() -> None:
    result = adapt_quotas_query(
        variation_is_none=True,
        item_quotas_source_id=10,
        variation_quotas_source_id=20,
        subevent_id=30,
    )

    assert result.source == SemanticReference(
        type_name="QuotaRelation",
        identity=10,
    )


def test_variation_quota_branch() -> None:
    result = adapt_quotas_query(
        variation_is_none=False,
        item_quotas_source_id=10,
        variation_quotas_source_id=20,
        subevent_id=30,
    )

    assert result.source == SemanticReference(
        type_name="QuotaRelation",
        identity=20,
    )


def test_subevent_filter_is_preserved() -> None:
    result = adapt_quotas_query(
        variation_is_none=True,
        item_quotas_source_id=10,
        variation_quotas_source_id=20,
        subevent_id=30,
    )

    assert result.predicates == (
        QueryPredicate(
            field="subevent",
            value=SemanticReference(
                type_name="Subevent",
                identity=30,
            ),
        ),
    )


def test_branch_mutant_is_refuted() -> None:
    correct = adapt_quotas_query(
        variation_is_none=True,
        item_quotas_source_id=10,
        variation_quotas_source_id=20,
        subevent_id=30,
    )

    mutant = mutant_quotas_query(
        variation_is_none=True,
        item_quotas_source_id=10,
        variation_quotas_source_id=20,
        subevent_id=30,
    )

    assert correct != mutant


def test_query_plan_fingerprint_is_stable() -> None:
    first = adapt_quotas_query(
        True,
        10,
        20,
        30,
    )

    second = adapt_quotas_query(
        True,
        10,
        20,
        30,
    )

    assert query_plan_fingerprint(first) == query_plan_fingerprint(second)

    assert '"kind":"QUERY_PLAN"' in query_plan_fingerprint(first)
