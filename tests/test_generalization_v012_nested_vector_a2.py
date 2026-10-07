from decimal import Decimal

from bizproof.generalization_v012_nested_vector_a2 import (
    ZoneCeiling,
    nested_family_vector_condition_return,
    nested_parameterized_select_return,
)

ZONE_A = ZoneCeiling(
    100,
    200,
    300,
    400,
    500,
    600,
    50,
)


def test_brs_fixed_ceiling() -> None:
    assert (
        nested_parameterized_select_return(
            zones_abc_eligibles=("A",),
            plafonds_par_zones={
                "A": ZONE_A,
            },
            zone_menage="A",
            nb_personnes=3,
            nb_personnes_max=6,
        )
        == 300
    )


def test_brs_supplementary_person() -> None:
    assert (
        nested_parameterized_select_return(
            zones_abc_eligibles=("A",),
            plafonds_par_zones={
                "A": ZONE_A,
            },
            zone_menage="A",
            nb_personnes=7,
            nb_personnes_max=6,
        )
        == 650
    )


def test_brs_unmatched_zone_returns_zero() -> None:
    assert (
        nested_parameterized_select_return(
            zones_abc_eligibles=("A",),
            plafonds_par_zones={
                "A": ZONE_A,
            },
            zone_menage="UNMATCHED",
            nb_personnes=4,
            nb_personnes_max=6,
        )
        == 0
    )


def test_rsa_majoration_threshold_path() -> None:
    assert (
        nested_family_vector_condition_return(
            enfant=True,
            age_lt_age_pac=True,
            autonomie_financiere=False,
            ressources=Decimal("40"),
            enceinte_fam=False,
            en_couple=False,
            isolement_recent=True,
            presence_autres_enfants=False,
            majoration_threshold=Decimal("50"),
            general_threshold=Decimal("30"),
        )
        == 1
    )


def test_rsa_general_threshold_path() -> None:
    assert (
        nested_family_vector_condition_return(
            enfant=True,
            age_lt_age_pac=True,
            autonomie_financiere=False,
            ressources=Decimal("40"),
            enceinte_fam=True,
            en_couple=False,
            isolement_recent=True,
            presence_autres_enfants=False,
            majoration_threshold=Decimal("50"),
            general_threshold=Decimal("30"),
        )
        == 0
    )
