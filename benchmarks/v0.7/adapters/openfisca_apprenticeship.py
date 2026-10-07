def is_apprenticeship_tax_liable(
    nonprofit_association: bool,
) -> bool:
    """Scalar semantic slice of OpenFisca redevable_taxe_apprentissage."""
    return not nonprofit_association


def mutant_is_apprenticeship_tax_liable(
    nonprofit_association: bool,
) -> bool:
    """Boundary mutation used only for sensitivity validation."""
    return nonprofit_association
