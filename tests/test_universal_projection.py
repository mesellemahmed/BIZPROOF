from pathlib import Path

from bizproof.universal_projection import (
    ObservationKind,
    ProjectionCapability,
    analyze_universal_projection,
)

ROOT = Path("benchmarks/v0.13/universal_projection/cases")


def _analyze(name: str):
    return analyze_universal_projection(ROOT / name)


def test_scalar_projection() -> None:
    result = _analyze("scalar.py")

    assert ProjectionCapability.SCALAR_VALUE in result.capabilities

    assert result.case_specific_routing is False


def test_structured_tuple_projection() -> None:
    result = _analyze("structured_tuple.py")

    assert ProjectionCapability.STRUCTURED_VALUE in result.capabilities

    paths = {
        item.path for item in result.observations if (item.kind is ObservationKind.RETURN_COMPONENT)
    }

    assert paths == {
        "return[0]",
        "return[1]",
    }


def test_structured_dict_projection() -> None:
    result = _analyze("structured_dict.py")

    assert ProjectionCapability.STRUCTURED_VALUE in result.capabilities

    paths = {
        item.path for item in result.observations if (item.kind is ObservationKind.RETURN_COMPONENT)
    }

    assert paths == {
        "return['original']",
        "return['adjusted']",
    }


def test_opaque_binding_projection() -> None:
    result = _analyze("opaque_binding.py")

    assert ProjectionCapability.OPAQUE_BINDING in result.capabilities

    bindings = [
        item for item in result.observations if (item.kind is ObservationKind.OPAQUE_ATTRIBUTE)
    ]

    assert len(bindings) == 1

    assert bindings[0].expression == "user.is_staff"

    assert bindings[0].symbol == "beta_0"


def test_nested_logic_projection() -> None:
    result = _analyze("nested_logic.py")

    assert ProjectionCapability.NESTED_LOGIC in result.capabilities


def test_state_effect_projection() -> None:
    result = _analyze("state_effect.py")

    assert ProjectionCapability.STATE_EFFECT in result.capabilities

    kinds = {item.kind for item in result.observations}

    assert ObservationKind.STATE_WRITE in kinds

    assert ObservationKind.EFFECT_CALL in kinds


def test_mixed_projection() -> None:
    result = _analyze("mixed.py")

    expected = {
        ProjectionCapability.STRUCTURED_VALUE,
        ProjectionCapability.OPAQUE_BINDING,
        ProjectionCapability.NESTED_LOGIC,
        ProjectionCapability.STATE_EFFECT,
    }

    assert expected <= set(result.capabilities)


def test_loop_is_explicitly_flagged() -> None:
    result = _analyze("unsupported_loop.py")

    assert "While" in (result.unsupported_nodes)


def test_no_case_specific_routing() -> None:
    for path in ROOT.glob("*.py"):
        result = analyze_universal_projection(path)

        assert result.case_specific_routing is False
