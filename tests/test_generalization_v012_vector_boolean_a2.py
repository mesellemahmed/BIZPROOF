from itertools import product

import pytest

from bizproof.generalization_v012_vector_boolean_a2 import (
    vector_boolean_where_return,
)


def test_exhaustive_boolean_basis() -> None:
    cases = list(
        product(
            (0, 1),
            (0, 1),
            (False, True),
            (False, True),
        )
    )

    result = vector_boolean_where_return(
        bourse_criteres_sociaux=[row[0] for row in cases],
        bourse_enseignement_sup=[row[1] for row in cases],
        has_parent_role=[row[2] for row in cases],
        eligibilite_per=[row[3] for row in cases],
    )

    assert len(result) == 16

    expected = tuple(
        ((social > 0 or higher > 0) and not (parent and eligible))
        for (
            social,
            higher,
            parent,
            eligible,
        ) in cases
    )

    assert result == expected

    assert sum(result) == 9


def test_parent_family_exclusion() -> None:
    result = vector_boolean_where_return(
        bourse_criteres_sociaux=[1],
        bourse_enseignement_sup=[0],
        has_parent_role=[True],
        eligibilite_per=[True],
    )

    assert result == (False,)


def test_scholarship_required_for_true_result() -> None:
    result = vector_boolean_where_return(
        bourse_criteres_sociaux=[0],
        bourse_enseignement_sup=[0],
        has_parent_role=[False],
        eligibilite_per=[False],
    )

    assert result == (False,)


def test_vector_length_gate() -> None:
    with pytest.raises(ValueError):
        vector_boolean_where_return(
            bourse_criteres_sociaux=[1],
            bourse_enseignement_sup=[
                1,
                0,
            ],
            has_parent_role=[True],
            eligibilite_per=[True],
        )
