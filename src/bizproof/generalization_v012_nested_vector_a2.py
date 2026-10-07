"""Nested finite-domain semantic projections for BIZPROOF V0.12."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ZoneCeiling:
    """Scalar parameter projection for one BRS zone."""

    nb_personnes_1: int
    nb_personnes_2: int
    nb_personnes_3: int
    nb_personnes_4: int
    nb_personnes_5: int
    nb_personnes_6: int
    nb_personnes_supplementaires: int


def nested_parameterized_select_return(
    *,
    zones_abc_eligibles: tuple[str, ...],
    plafonds_par_zones: dict[str, ZoneCeiling],
    zone_menage: str,
    nb_personnes: int,
    nb_personnes_max: int,
) -> int:
    """Accepted scalar projection of the BRS nested select formula."""
    if zone_menage not in zones_abc_eligibles:
        return 0

    plafond_zone = plafonds_par_zones[zone_menage]

    fixed = (
        plafond_zone.nb_personnes_1,
        plafond_zone.nb_personnes_2,
        plafond_zone.nb_personnes_3,
        plafond_zone.nb_personnes_4,
        plafond_zone.nb_personnes_5,
        plafond_zone.nb_personnes_6,
    )

    if nb_personnes <= 0:
        plafond_base = 0
    elif nb_personnes < 6:
        plafond_base = fixed[nb_personnes - 1]
    else:
        plafond_base = fixed[5]

    plafond_supp = (
        (nb_personnes - nb_personnes_max) * plafond_zone.nb_personnes_supplementaires
        if (nb_personnes > nb_personnes_max)
        else 0
    )

    return plafond_base + plafond_supp


def nested_family_vector_condition_return(
    *,
    enfant: bool,
    age_lt_age_pac: bool,
    autonomie_financiere: bool,
    ressources: Decimal,
    enceinte_fam: bool,
    en_couple: bool,
    isolement_recent: bool,
    presence_autres_enfants: bool,
    majoration_threshold: Decimal,
    general_threshold: Decimal,
) -> int:
    """Accepted scalar/family-aggregate projection of RSA child charge."""
    ouvre_droit_majoration = (
        (not enceinte_fam)
        and (not en_couple)
        and isolement_recent
        and (not presence_autres_enfants)
    )

    resource_gate = (
        ressources < majoration_threshold
        if ouvre_droit_majoration
        else ressources < general_threshold
    )

    return int(enfant and (not autonomie_financiere) and age_lt_age_pac and resource_gate)
