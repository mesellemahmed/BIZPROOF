from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_runner():
    path = Path(__file__).resolve().parents[1] / "src/bizproof/adapter_preservation.py"
    spec = importlib.util.spec_from_file_location("_adapter_preservation_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_v08_partition_sums_are_preserved() -> None:
    runner = _load_runner()
    for total in range(50):
        for partition in runner._partitions(total):
            assert sum(partition) == total


def test_v08_extracts_original_method_body(tmp_path: Path) -> None:
    runner = _load_runner()
    source = tmp_path / "external.py"
    source.write_text(
        "class Rule:\n"
        "    def evaluate(self, source, period):\n"
        "        value = source('amount', period)\n"
        "        return max_(value - 2, 0)\n",
        encoding="utf-8",
    )
    method = runner._extract_method(
        source,
        class_name="Rule",
        method_name="evaluate",
        namespace={"max_": max},
    )
    lookup = runner._Lookup({"amount": 5})
    assert method.function(object(), lookup, object()) == 3
    assert method.line_start == 2
    assert method.line_end == 4
    assert len(method.method_sha256) == 64


def test_v08_mutant_sensitivity_boolean() -> None:
    runner = _load_runner()

    def external(source, period):
        del period
        return not source("entreprise_est_association_non_lucrative", object())

    result = runner._run_apprenticeship(
        external,
        lambda flag: not flag,
        lambda flag: flag,
    )
    assert result["comparisons"] == 2
    assert result["correct_mismatches"] == 0
    assert result["mutant_mismatches"] == 2
