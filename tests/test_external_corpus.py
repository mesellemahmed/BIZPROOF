from __future__ import annotations

import json
from pathlib import Path

from bizproof.external_corpus import run_external_audit


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_exact_evidence_provenance(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external"
    repo = external / "sample"

    _write(
        repo / "src/pricing.py",
        """
def discount_allowed(amount: int, vip: bool) -> bool:
    return vip or amount >= 100

def tax_total(order):
    return order.total * order.tax_rate

def payment_retry(payments):
    for payment in payments:
        if payment:
            return True
    return False
""".strip()
        + "\n",
    )

    _write(
        repo / "src/tax_credit.py",
        """
class tax_credit:
    def formula(amount: int) -> bool:
        return amount >= 50
""".strip()
        + "\n",
    )

    _write(
        repo / "tests/test_pricing.py",
        """
from pricing import discount_allowed

def test_discount_allowed():
    assert discount_allowed(100, False)
""".strip()
        + "\n",
    )

    _write(
        repo / "tests/test_noise.py",
        """
def test_unrelated():
    assert "discount price tax total"
""".strip()
        + "\n",
    )

    _write(
        repo / "tests/tax_credit.yaml",
        """
- name: tax credit threshold
  input:
    amount: 50
  output:
    tax_credit: true
""".strip()
        + "\n",
    )

    sources = {
        "sources": [
            {
                "id": "sample",
                "name": "Sample",
                "repository": "x",
                "ref": "main",
                "domain": "ecommerce",
                "license": "MIT",
                "code_roots": ["src"],
                "test_roots": ["tests"],
                "doc_roots": [],
                "max_code_files": 20,
            }
        ]
    }

    lock = {
        "sources": [
            {
                "id": "sample",
                "resolved_commit": "abc123",
            }
        ]
    }

    sources_path = tmp_path / "sources.json"
    lock_path = tmp_path / "LOCK.json"
    output = tmp_path / "results"

    sources_path.write_text(
        json.dumps(sources),
        encoding="utf-8",
    )
    lock_path.write_text(
        json.dumps(lock),
        encoding="utf-8",
    )

    summary = run_external_audit(
        sources_path=sources_path,
        lock_path=lock_path,
        external_root=external,
        output_dir=output,
    )

    assert summary["functions_examined"] == 4
    assert summary["business_candidates"] == 4
    assert summary["direct_candidates"] == 2
    assert summary["adaptation_required"] == 1
    assert summary["unsupported"] == 1

    records = [
        json.loads(line)
        for line in (output / "candidates.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    by_key = {
        (
            record["function"],
            record["file"],
        ): record
        for record in records
    }

    discount = by_key[("discount_allowed", "src/pricing.py")]
    assert discount["supporting_test_files"] == ["tests/test_pricing.py"]
    assert discount["evidence_link_modes"]["test:EXACT_FUNCTION_SYMBOL"] == 1

    tax_total = by_key[("tax_total", "src/pricing.py")]
    assert tax_total["supporting_test_files"] == []

    formula = by_key[("formula", "src/tax_credit.py")]
    assert formula["enclosing_class"] == "tax_credit"
    assert formula["business_relevance"] == "STRONG"
    assert formula["supporting_test_files"] == ["tests/tax_credit.yaml"]
    assert formula["evidence_link_modes"]["test:EXACT_CLASS_TEXT"] == 1


def test_broad_source_test_root_filters_production_files(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external"
    repo = external / "sample"

    _write(
        repo / "src/orders.py",
        """
def order_total(amount: int) -> int:
    return amount
""".strip()
        + "\n",
    )

    _write(
        repo / "src/helpers.py",
        """
def helper():
    return "order_total"
""".strip()
        + "\n",
    )

    _write(
        repo / "src/tests/test_orders.py",
        """
from orders import order_total

def test_order_total():
    assert order_total(10) == 10
""".strip()
        + "\n",
    )

    sources = {
        "sources": [
            {
                "id": "sample",
                "name": "Sample",
                "repository": "x",
                "ref": "main",
                "domain": "orders",
                "license": "MIT",
                "code_roots": ["src"],
                "test_roots": ["src"],
                "doc_roots": [],
                "max_code_files": 20,
            }
        ]
    }

    lock = {
        "sources": [
            {
                "id": "sample",
                "resolved_commit": "abc",
            }
        ]
    }

    sources_path = tmp_path / "sources.json"
    lock_path = tmp_path / "LOCK.json"
    output = tmp_path / "out"

    sources_path.write_text(
        json.dumps(sources),
        encoding="utf-8",
    )
    lock_path.write_text(
        json.dumps(lock),
        encoding="utf-8",
    )

    run_external_audit(
        sources_path=sources_path,
        lock_path=lock_path,
        external_root=external,
        output_dir=output,
    )

    records = [
        json.loads(line)
        for line in (output / "candidates.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    order = next(record for record in records if record["function"] == "order_total")

    assert order["supporting_test_files"] == ["src/tests/test_orders.py"]
