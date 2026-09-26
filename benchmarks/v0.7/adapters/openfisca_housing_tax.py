def housing_tax_after_relief(
    tax_before_relief: int,
    relief: int,
) -> int:
    """Integer monetary-unit slice of the OpenFisca clamped subtraction."""
    if tax_before_relief - relief > 0:
        return tax_before_relief - relief
    return 0


def mutant_housing_tax_after_relief(
    tax_before_relief: int,
    relief: int,
) -> int:
    """Mutation that incorrectly permits a negative tax result."""
    return tax_before_relief - relief
