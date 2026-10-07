from __future__ import annotations

import importlib
from typing import Any

import z3


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_a1_batch_proof")


def test_canonical_expression() -> None:

    module = _module()

    assert (
        module._canonical_expression('foyer_fiscal("rbg", period)') == "foyer_fiscal('rbg', period)"
    )


def test_source_and_bsir_simple_add_are_equivalent() -> None:

    module = _module()

    left = z3.Real("left")

    right = z3.Real("right")

    bindings = {
        "foyer_fiscal('a', period)": left,
        "foyer_fiscal('b', period)": right,
    }

    compiler = module.SourceCompiler(bindings)

    source = """
def formula(foyer_fiscal, period):
    a = foyer_fiscal('a', period)
    b = foyer_fiscal('b', period)
    return a + b
"""

    source_expr = compiler.function(source)

    ir = {
        "op": "add",
        "left": {
            "op": "binding",
            "binding_id": "a",
        },
        "right": {
            "op": "binding",
            "binding_id": "b",
        },
    }

    ir_expr = module._compile_ir(
        ir,
        {
            "a": left,
            "b": right,
        },
    )

    solver = z3.Solver()

    solver.add(source_expr != ir_expr)

    assert solver.check() == z3.unsat


def test_direct_binding_mutant_is_detectable() -> None:

    module = _module()

    original = {
        "op": "binding",
        "binding_id": "x",
    }

    mutated, description = module._mutate_ir(original)

    x = z3.Real("x")

    original_expr = module._compile_ir(
        original,
        {
            "x": x,
        },
    )

    mutant_expr = module._compile_ir(
        mutated,
        {
            "x": x,
        },
    )

    solver = z3.Solver()

    solver.add(original_expr != mutant_expr)

    assert solver.check() == z3.sat

    assert description
