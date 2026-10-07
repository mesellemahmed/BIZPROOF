from pathlib import Path

from bizproof.universal_closure import (
    certify_universal,
)

ROOT = Path("benchmarks/v0.13/universal_closure/cases")


def _certify(name: str):
    return certify_universal(
        source_file=ROOT / name,
        evidence_id=("test::" + name),
    )


def test_structured_tuple_certified() -> None:
    result = _certify("structured_tuple.py")

    assert result["certified"] is True

    assert result["scientific_outcome"] == "CERTIFIED_A2"

    assert result["formal_obligation_count"] == 2


def test_structured_dict_certified() -> None:
    result = _certify("structured_dict.py")

    assert result["certified"] is True

    assert result["formal_obligation_count"] == 2


def test_opaque_binding_parametric() -> None:
    result = _certify("opaque_binding.py")

    assert result["certified"] is True

    expressions = {item["expression"] for item in result["bindings"]}

    assert "user.is_staff" in expressions


def test_nested_logic_certified() -> None:
    result = _certify("nested_logic.py")

    assert result["certified"] is True

    assert result["scientific_outcome"] in {
        "CERTIFIED_A1",
        "CERTIFIED_A2",
    }


def test_state_effect_is_capped_at_a1() -> None:
    result = _certify("state_effect.py")

    assert result["certified"] is True

    assert result["scientific_outcome"] == "CERTIFIED_A1"

    assert result["effects"]

    assert result["effect_semantics_formally_proved"] is False


def test_mixed_capabilities_certified_a1() -> None:
    result = _certify("mixed.py")

    assert result["certified"] is True

    assert result["scientific_outcome"] == "CERTIFIED_A1"

    assert result["effects"]


def test_loop_stays_unsupported() -> None:
    result = _certify("unsupported_loop.py")

    assert result["certified"] is False

    assert result["scientific_outcome"] == "UNSUPPORTED"


def test_no_case_specific_routing() -> None:
    for path in ROOT.glob("*.py"):
        result = certify_universal(
            source_file=path,
            evidence_id=("routing::" + path.name),
        )

        assert result["case_specific_routing"] is False
