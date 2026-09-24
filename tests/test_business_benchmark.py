from pathlib import Path

from bizproof.business_benchmark import (
    expression_matches_oracle,
    implementation_variants,
    load_catalog,
    run_benchmark,
    validate_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "benchmarks" / "v0.3" / "catalog.json"


def test_v03_catalog_integrity() -> None:
    catalog = load_catalog(CATALOG)
    validate_catalog(catalog)
    rules = catalog["rules"]

    assert len(rules) == 60
    assert sum(rule["domain"] == "banking" for rule in rules) == 20
    assert sum(rule["domain"] == "ecommerce" for rule in rules) == 20
    assert sum(rule["domain"] == "insurance" for rule in rules) == 20


def test_all_declared_mutants_are_non_equivalent() -> None:
    catalog = load_catalog(CATALOG)
    for rule in catalog["rules"]:
        variants = implementation_variants(rule)
        assert len(variants) == 5
        assert variants[0][0] == "correct"
        assert expression_matches_oracle(rule, variants[0][1])
        for name, expression in variants[1:]:
            assert name != "correct"
            assert not expression_matches_oracle(rule, expression)


def test_small_business_benchmark(tmp_path: Path) -> None:
    summary = run_benchmark(
        CATALOG,
        tmp_path / "summary.json",
        max_rules=3,
        mutants_per_rule=1,
    )

    assert summary["passed"] is True
    assert summary["rules_checked"] == 3
    assert summary["cases_checked"] == 6
    assert summary["z3_false_proved"] == 0
    assert summary["enum_z3_verdict_disagreements"] == 0
