from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import z3


def _load_module() -> Any:
    """Import the module through its real package context."""
    return importlib.import_module("bizproof.symbolic_equivalence")


def test_symbolic_equivalence_proves_identical_predicate() -> None:
    module = _load_module()

    x = z3.Int("x")
    inputs = {
        "x": {
            "type": "int",
            "min": 0,
            "max": 10,
        }
    }

    result = module._prove_equivalence(
        x >= 5,
        x >= 5,
        [x >= 0, x <= 10],
        inputs,
        {"x": x},
    )

    assert result["verdict"] == "PROVED"
    assert result["counterexample"] is None


def test_symbolic_equivalence_returns_counterexample() -> None:
    module = _load_module()

    x = z3.Int("x")
    inputs = {
        "x": {
            "type": "int",
            "min": 0,
            "max": 10,
        }
    }

    result = module._prove_equivalence(
        x >= 5,
        x > 5,
        [x >= 0, x <= 10],
        inputs,
        {"x": x},
    )

    assert result["verdict"] == "DISPROVED"
    assert result["counterexample"] == {"x": 5}


def test_function_compiler_supports_simple_if_return(
    tmp_path: Path,
) -> None:
    module = _load_module()

    path = tmp_path / "adapter.py"
    path.write_text(
        "def clamp(value: int) -> int:\n    if value > 0:\n        return value\n    return 0\n",
        encoding="utf-8",
    )

    source, function = module._find_function(
        path,
        "clamp",
    )

    value = z3.Int("value")
    ctx = module.SymbolicContext(
        symbols={"value": value},
        call_bindings={},
        attribute_bindings={},
        method_call_bindings={},
    )

    expression = module._compile_statements(
        function.body,
        ctx,
    )

    solver = z3.Solver()
    solver.add(expression != z3.If(value > 0, value, 0))

    assert solver.check() == z3.unsat
    assert len(module._node_hash(source, function)) == 64
