from bizproof.generalization_v012_large_domain_binding_a2 import (
    DateValue,
    MobilityParameters,
    large_bound_domain_vector_return,
)

PARAMS = MobilityParameters(
    delai_max=7,
    duree_de_formation_minimum=40,
    duree_de_contrat_minimum=3,
    duree_trajet_minimum=90,
    distance_minimum_metropole=60,
    distance_minimum_hors_metropole=40,
)


def base() -> dict[str, object]:
    return {
        "contexte": "recherche_emploi",
        "contrat_travail_debut": DateValue(
            2024,
            1,
            31,
        ),
        "date_debut_recherche_emploi": DateValue(
            2024,
            1,
            10,
        ),
        "aide_mobilite_date_demande": DateValue(
            2024,
            1,
            15,
        ),
        "types_activite_en_recherche_emploi": "autre",
        "contrat_de_travail_type": "autre",
        "formation_validee_pole_emploi": True,
        "formation_financee_ou_cofinancee": True,
        "duree_formation": 40,
        "contrat_de_travail_duree": 3,
        "categories_demandeur_emploi_eligibles": True,
        "ressources_eligibles": True,
        "lieu_emploi_ou_formation": "renseigne",
        "residence": "metropole",
        "duree_trajet": 30,
        "distance_activite_domicile": 31,
        "dispositifs_formation": "autre",
        "parameters": PARAMS,
    }


def evaluate(
    **changes: object,
) -> int:
    values = base()
    values.update(changes)

    return large_bound_domain_vector_return(
        **values  # type: ignore[arg-type]
    )


def test_search_baseline() -> None:
    assert evaluate() == 1


def test_search_date_boundary() -> None:
    assert (
        evaluate(
            aide_mobilite_date_demande=DateValue(
                2024,
                1,
                16,
            )
        )
        == 1
    )

    assert (
        evaluate(
            aide_mobilite_date_demande=DateValue(
                2024,
                1,
                17,
            )
        )
        == 0
    )


def test_month_end_capping() -> None:
    assert (
        evaluate(
            contexte="reprise_emploi",
            contrat_de_travail_type="cdi",
            aide_mobilite_date_demande=DateValue(
                2024,
                2,
                29,
            ),
        )
        == 1
    )

    assert (
        evaluate(
            contexte="reprise_emploi",
            contrat_de_travail_type="cdi",
            aide_mobilite_date_demande=DateValue(
                2024,
                3,
                1,
            ),
        )
        == 0
    )


def test_travel_time_only_path() -> None:
    assert (
        evaluate(
            distance_activite_domicile=10,
            duree_trajet=91,
        )
        == 1
    )


def test_strict_travel_boundary() -> None:
    assert (
        evaluate(
            distance_activite_domicile=30,
            duree_trajet=90,
        )
        == 0
    )
