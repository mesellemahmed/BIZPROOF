def count_condition_partially_satisfied(
    num_matches: int,
    required_count: int,
) -> bool:
    """Post-aggregation scalar slice of Django-Oscar CountCondition."""
    return (num_matches > 0) and (num_matches < required_count)


def mutant_count_condition_partially_satisfied(
    num_matches: int,
    required_count: int,
) -> bool:
    """Boundary mutation that incorrectly accepts an exactly satisfied count."""
    return (num_matches > 0) and (num_matches <= required_count)
