from bizproof.compositional_helper_runtime_v012 import (
    AttributeTree,
    ControlledHelperEnvironment,
    build_final_composition_mutant,
    execute_final_composition_mutant,
    execute_frozen_formula,
)


def test_attribute_tree() -> None:
    tree = AttributeTree(
        {
            "a.b.c": 42,
        }
    )

    assert tree.a.b.c == 42


def test_exact_source_execution() -> None:
    source = """
def formula(famille, period, parameters):
    value = famille('x', period)
    limit = parameters(period).section.limit
    return value + limit
"""

    env = ControlledHelperEnvironment(
        family_scalars={
            "x": 3,
        },
        family_members={},
        parameter_values={
            "section.limit": 7,
        },
        child_counts={},
    )

    assert (
        execute_frozen_formula(
            source,
            "formula",
            env,
        )
        == 10
    )


def test_mutation_builder_changes_only_target_formula() -> None:
    source = """
def formula(famille, period, parameters):
    eligible = famille('eligible', period)
    amount = parameters(period).amount
    result = eligible * amount
    return result
"""

    mutant = build_final_composition_mutant(
        source,
        target_name="result",
    )

    assert "result = eligible + amount" in mutant


def test_full_mutant_replay() -> None:
    source = """
def formula(famille, period, parameters):
    eligible = famille('eligible', period)
    amount = parameters(period).amount
    result = eligible * amount
    return result
"""

    env = ControlledHelperEnvironment(
        family_scalars={
            "eligible": 1,
        },
        family_members={},
        parameter_values={
            "amount": 50,
        },
        child_counts={},
    )

    correct = execute_frozen_formula(
        source,
        "formula",
        env,
    )

    mutant = execute_final_composition_mutant(
        source,
        "formula",
        env,
        target_name="result",
    )

    assert correct == 50
    assert mutant == 51
    assert correct != mutant
