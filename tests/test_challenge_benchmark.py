from pathlib import Path

from bizproof.challenge_benchmark import (
    domain_size,
    load_catalog,
    mutant_expression,
    reference_expression,
    reference_value,
    validate_catalog,
    witness_count,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "benchmarks" / "v0.5" / "catalog.json"


def test_challenge_catalog_is_balanced_and_valid() -> None:
    catalog = load_catalog(CATALOG)
    validate_catalog(catalog)
    rules = catalog["rules"]
    assert len(rules) == 30
    assert sum(1 for rule in rules if rule["domain"] == "banking") == 10
    assert sum(1 for rule in rules if rule["domain"] == "ecommerce") == 10
    assert sum(1 for rule in rules if rule["domain"] == "insurance") == 10


def test_every_challenge_mutant_has_rare_witnesses() -> None:
    catalog = load_catalog(CATALOG)
    for rule in catalog["rules"]:
        size = domain_size(rule)
        witnesses = witness_count(rule)
        assert witnesses > 0
        assert witnesses < size
        assert witnesses / size < 0.02
        assert reference_expression(rule) != mutant_expression(rule)


def test_narrow_boundary_has_single_witness() -> None:
    catalog = load_catalog(CATALOG)
    rule = next(rule for rule in catalog["rules"] if rule["family"] == "narrow_boundary")
    assert witness_count(rule) == 1


def _known_reference_witness(rule: dict[str, object]) -> dict[str, object]:
    family = rule["family"]
    params = rule["params"]
    assert isinstance(params, dict)

    if family == "single_magic":
        return {"x": params["target"]}
    if family == "pair_magic":
        return {"x": params["target_x"], "y": params["target_y"]}
    if family == "narrow_boundary":
        return {"x": params["low"]}
    if family == "guarded_magic":
        return {"x": params["target"], "flag": True}
    if family == "linear_magic":
        return {"x": 0, "y": params["target"]}
    if family == "triple_magic":
        return {
            "x": params["target_x"],
            "y": params["target_y"],
            "z": params["target_z"],
        }
    raise AssertionError(f"unsupported family: {family}")


def test_reference_oracle_matches_each_family_witness() -> None:
    catalog = load_catalog(CATALOG)
    for rule in catalog["rules"]:
        witness = _known_reference_witness(rule)
        assert reference_value(rule, witness) is False
