"""Finite vector-boolean semantic projection for BIZPROOF V0.12."""

from __future__ import annotations

from collections.abc import Sequence


def vector_boolean_where_return(
    *,
    bourse_criteres_sociaux: Sequence[int],
    bourse_enseignement_sup: Sequence[int],
    has_parent_role: Sequence[bool],
    eligibilite_per: Sequence[bool],
) -> tuple[bool, ...]:
    """Evaluate the accepted formula_2022 vector projection."""
    lengths = {
        len(bourse_criteres_sociaux),
        len(bourse_enseignement_sup),
        len(has_parent_role),
        len(eligibilite_per),
    }

    if len(lengths) != 1:
        raise ValueError("all vector observations must have equal length")

    result: list[bool] = []

    for (
        social,
        higher,
        parent,
        family_eligible,
    ) in zip(
        bourse_criteres_sociaux,
        bourse_enseignement_sup,
        has_parent_role,
        eligibilite_per,
        strict=True,
    ):
        scholarship_any = social > 0 or higher > 0

        outer_condition = not scholarship_any

        inner_result = False if (parent and family_eligible) else True

        result.append(False if outer_condition else inner_result)

    return tuple(result)
