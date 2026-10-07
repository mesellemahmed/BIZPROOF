def count_condition_satisfied(
    num_matches: int,
    required_count: int,
) -> bool:
    """Post-aggregation threshold slice of Django-Oscar CountCondition."""
    return num_matches >= required_count


def mutant_count_condition_satisfied(
    num_matches: int,
    required_count: int,
) -> bool:
    """Boundary mutation that rejects the exact threshold."""
    return num_matches > required_count
