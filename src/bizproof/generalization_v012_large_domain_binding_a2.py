"""Large finite-domain binding projection for BIZPROOF V0.12."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class DayDelta:
    """Integer day delta used by the exact-source date harness."""

    days: int


@dataclass(frozen=True, slots=True)
class MonthValue:
    """Month-resolution date value."""

    year: int
    month: int

    def __add__(
        self,
        other: object,
    ) -> MonthValue | DateValue:
        if isinstance(
            other,
            int,
        ):
            index = self.year * 12 + self.month - 1 + other

            return MonthValue(
                index // 12,
                index % 12 + 1,
            )

        if isinstance(
            other,
            DayDelta,
        ):
            base = date(
                self.year,
                self.month,
                1,
            )

            value = base + timedelta(days=other.days)

            return DateValue(
                value.year,
                value.month,
                value.day,
            )

        raise TypeError(type(other))

    def __sub__(
        self,
        other: object,
    ) -> DateValue:
        if not isinstance(
            other,
            DayDelta,
        ):
            raise TypeError(type(other))

        base = date(
            self.year,
            self.month,
            1,
        )

        value = base - timedelta(days=other.days)

        return DateValue(
            value.year,
            value.month,
            value.day,
        )


@dataclass(
    frozen=True,
    order=True,
    slots=True,
)
class DateValue:
    """Scalar day-resolution date with numpy-like operations."""

    year: int
    month: int
    day: int

    def _date(
        self,
    ) -> date:
        return date(
            self.year,
            self.month,
            self.day,
        )

    def astype(
        self,
        fmt: str,
    ) -> MonthValue:
        if fmt != "M8[M]":
            raise ValueError(fmt)

        return MonthValue(
            self.year,
            self.month,
        )

    def __add__(
        self,
        other: object,
    ) -> DateValue:
        if isinstance(
            other,
            int,
        ):
            days = other
        elif isinstance(
            other,
            DayDelta,
        ):
            days = other.days
        else:
            raise TypeError(type(other))

        value = self._date() + timedelta(days=days)

        return DateValue(
            value.year,
            value.month,
            value.day,
        )

    def __sub__(
        self,
        other: object,
    ) -> DayDelta:
        if isinstance(
            other,
            DateValue,
        ):
            base = other._date()
        elif isinstance(
            other,
            MonthValue,
        ):
            base = date(
                other.year,
                other.month,
                1,
            )
        else:
            raise TypeError(type(other))

        return DayDelta((self._date() - base).days)


@dataclass(frozen=True, slots=True)
class MobilityParameters:
    """Frozen parameter projection used by formula_2021_06_09."""

    delai_max: int
    duree_de_formation_minimum: int
    duree_de_contrat_minimum: int
    duree_trajet_minimum: int
    distance_minimum_metropole: int
    distance_minimum_hors_metropole: int


def _shift_month(
    value: MonthValue,
    offset: int,
) -> MonthValue:
    index = value.year * 12 + value.month - 1 + offset

    return MonthValue(
        index // 12,
        index % 12 + 1,
    )


def _one_month_capped(
    value: DateValue,
) -> DateValue:
    month = MonthValue(
        value.year,
        value.month,
    )

    offset = value - month

    candidate = (
        _shift_month(
            month,
            1,
        )
        + offset
    )

    end_of_next_month = _shift_month(
        month,
        2,
    ) - DayDelta(1)

    assert isinstance(
        candidate,
        DateValue,
    )

    return min(
        candidate,
        end_of_next_month,
    )


def large_bound_domain_vector_return(
    *,
    contexte: str,
    contrat_travail_debut: DateValue,
    date_debut_recherche_emploi: DateValue,
    aide_mobilite_date_demande: DateValue,
    types_activite_en_recherche_emploi: str,
    contrat_de_travail_type: str,
    formation_validee_pole_emploi: bool,
    formation_financee_ou_cofinancee: bool,
    duree_formation: int,
    contrat_de_travail_duree: int,
    categories_demandeur_emploi_eligibles: bool,
    ressources_eligibles: bool,
    lieu_emploi_ou_formation: str,
    residence: str,
    duree_trajet: int,
    distance_activite_domicile: int,
    dispositifs_formation: str,
    parameters: MobilityParameters,
) -> int:
    """Evaluate the accepted scalar projection of the mobility rule."""
    recherche = contexte == "recherche_emploi"

    reprise = contexte == "reprise_emploi"

    formation = contexte == "formation"

    formation_reprise_limit = _one_month_capped(contrat_travail_debut)

    formation_reprise_date_ok = aide_mobilite_date_demande <= formation_reprise_limit

    search_limit = date_debut_recherche_emploi + (parameters.delai_max - 1)

    search_date_ok = aide_mobilite_date_demande <= search_limit

    contextes_eligibles = int(recherche) * int(search_date_ok) + (
        int(reprise) + int(formation)
    ) * int(formation_reprise_date_ok)

    entretien = types_activite_en_recherche_emploi == "entretien_embauche"

    indeterminee = types_activite_en_recherche_emploi == "indeterminee"

    en_entretien_embauche = int(entretien) * int(recherche)

    recherche_activite_eligible = int(not (int(entretien) + int(indeterminee))) * int(recherche)

    type_formation = contrat_de_travail_type == "formation"

    type_cdi = contrat_de_travail_type == "cdi"

    type_cdd_ctt = int(contrat_de_travail_type == "cdd") + int(contrat_de_travail_type == "ctt")

    formation_duration_ok = duree_formation >= parameters.duree_de_formation_minimum

    contract_duration_ok = contrat_de_travail_duree >= parameters.duree_de_contrat_minimum

    eligible_cdd_ctt = type_cdd_ctt * int(contract_duration_ok)

    types_et_duree = (int(type_cdi) + eligible_cdd_ctt) * (int(reprise) + en_entretien_embauche) + (
        int(type_formation)
        * int(formation)
        * int(formation_validee_pole_emploi)
        * int(formation_financee_ou_cofinancee)
        * int(formation_duration_ok)
    )

    activites_eligibles = types_et_duree + recherche_activite_eligible

    lieu_activite_eligible = lieu_emploi_ou_formation != "non_renseigne"

    reside_en_metropole = residence == "metropole"

    residence_renseignee = residence != "non_renseigne"

    distance_aller_retour = distance_activite_domicile * 2

    distances_et_durees = (
        int(distance_aller_retour > parameters.distance_minimum_metropole)
        * int(reside_en_metropole)
        + int(distance_aller_retour > parameters.distance_minimum_hors_metropole)
        * (int(not reside_en_metropole) * int(residence_renseignee))
        + int(duree_trajet > parameters.duree_trajet_minimum) * int(residence_renseignee)
    )

    dispositif_eligible = dispositifs_formation == "autre"

    return (
        contextes_eligibles
        * activites_eligibles
        * int(categories_demandeur_emploi_eligibles)
        * int(ressources_eligibles)
        * int(lieu_activite_eligible)
        * distances_et_durees
        * int(dispositif_eligible)
    )
