from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

JsonDict = dict[str, Any]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> JsonDict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_module(path: Path) -> ModuleType:
    name = f"_bizproof_adapter_{_sha256_file(path)[:16]}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load adapter module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class ExtractedMethod:
    function: Callable[..., Any]
    line_start: int
    line_end: int
    source_sha256: str
    method_sha256: str


def _extract_method(
    path: Path,
    *,
    class_name: str,
    method_name: str,
    namespace: dict[str, Any],
) -> ExtractedMethod:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    class_node: ast.ClassDef | None = None
    method_node: ast.FunctionDef | None = None

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            class_node = node
            break
    if class_node is None:
        raise ValueError(f"class {class_name!r} not found in {path}")

    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            method_node = node
            break
    if method_node is None:
        raise ValueError(f"method {class_name}.{method_name} not found in {path}")

    clean = copy.deepcopy(method_node)
    clean.decorator_list = []
    module = ast.Module(body=[clean], type_ignores=[])
    ast.fix_missing_locations(module)

    execution_namespace = dict(namespace)
    exec(compile(module, str(path), "exec"), execution_namespace)

    segment = ast.get_source_segment(source, method_node) or ""
    return ExtractedMethod(
        function=execution_namespace[method_name],
        line_start=method_node.lineno,
        line_end=getattr(method_node, "end_lineno", method_node.lineno),
        source_sha256=_sha256_file(path),
        method_sha256=_sha256_bytes(segment.encode("utf-8")),
    )


def _checkout_commit(repo: Path) -> str:
    """Resolve HEAD without requiring the git executable.

    V0.6 acquisition checks out each external repository in detached-HEAD
    mode. A symbolic-ref fallback is retained for robustness.
    """

    git_path = repo / ".git"

    if git_path.is_file():
        content = git_path.read_text(
            encoding="utf-8",
        ).strip()

        prefix = "gitdir:"

        if not content.lower().startswith(prefix):
            raise ValueError(f"invalid .git indirection file: {git_path}")

        raw = content[len(prefix) :].strip()
        git_dir = Path(raw)

        if not git_dir.is_absolute():
            git_dir = (git_path.parent / git_dir).resolve()

    else:
        git_dir = git_path

    head_path = git_dir / "HEAD"

    if not head_path.is_file():
        raise ValueError(f"Git HEAD file missing: {head_path}")

    head = head_path.read_text(
        encoding="utf-8",
    ).strip()

    if not head.startswith("ref:"):
        if len(head) != 40:
            raise ValueError(f"unexpected detached HEAD value: {head!r}")

        return head

    ref_name = head.removeprefix("ref:").strip()

    ref_path = git_dir / ref_name

    if ref_path.is_file():
        return ref_path.read_text(
            encoding="utf-8",
        ).strip()

    packed_refs = git_dir / "packed-refs"

    if packed_refs.is_file():
        for line in packed_refs.read_text(
            encoding="utf-8",
            errors="ignore",
        ).splitlines():
            if not line or line.startswith("#") or line.startswith("^"):
                continue

            sha, _, name = line.partition(" ")

            if name == ref_name:
                return sha

    raise ValueError(f"cannot resolve Git ref: {ref_name}")


class _Lookup:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values

    def __call__(self, name: str, _period: object, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return self.values[name]


class _PartialSelf:
    def __init__(self, *, value: int, num_matches: int) -> None:
        self.value = value
        self.num_matches = num_matches

    def _get_num_matches(self, _basket: object, _offer: object) -> int:
        return self.num_matches


class _Line:
    def __init__(self, quantity: int, *, applicable: bool = True) -> None:
        self.quantity = quantity
        self.applicable = applicable

    def quantity_without_offer_discount(self, _offer: object) -> int:
        return self.quantity


class _Basket:
    def __init__(self, lines: list[_Line]) -> None:
        self.lines = lines

    def all_lines(self) -> list[_Line]:
        return self.lines


class _SatisfiedSelf:
    def __init__(self, value: int) -> None:
        self.value = value

    @staticmethod
    def can_apply_condition(line: _Line) -> bool:
        return line.applicable


def _partitions(total: int) -> list[list[int]]:
    if total == 0:
        return [[], [0]]
    result = [[total]]
    if total >= 2:
        left = total // 2
        result.append([left, total - left])
    result.append([1] * total if total <= 8 else [1, 2, total - 3])
    unique: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    for item in result:
        key = tuple(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _compare(
    external: Any,
    adapter: Any,
    inputs: JsonDict,
    count: int,
    first: JsonDict | None,
) -> tuple[int, JsonDict | None]:
    if external == adapter:
        return count, first
    count += 1
    if first is None:
        first = {"inputs": inputs, "external": external, "adapter": adapter}
    return count, first


def _run_apprenticeship(
    method: Callable[..., Any],
    adapter: Callable[..., Any],
    mutant: Callable[..., Any],
) -> JsonDict:
    cm = mm = comparisons = 0
    fc = fm = None
    for association in (False, True):
        lookup = _Lookup({"entreprise_est_association_non_lucrative": association})
        external = method(lookup, object())
        inputs = {"nonprofit_association": association}
        comparisons += 1
        cm, fc = _compare(external, adapter(association), inputs, cm, fc)
        mm, fm = _compare(external, mutant(association), inputs, mm, fm)
    return {
        "comparisons": comparisons,
        "correct_mismatches": cm,
        "mutant_mismatches": mm,
        "first_correct_mismatch": fc,
        "first_mutant_mismatch": fm,
    }


def _housing_pairs(
    seed: int,
    maximum: int,
    random_cases: int,
) -> list[tuple[int, int]]:
    b = [0, 1, 2, 9, 10, 99, 100, 999, 1000, 9999, 10000, 999999, maximum]
    pairs = {(x, y) for x in b for y in b}
    rng = random.Random(seed)
    for _ in range(random_cases):
        pairs.add((rng.randint(0, maximum), rng.randint(0, maximum)))
    return sorted(pairs)


def _run_housing(
    method: Callable[..., Any],
    adapter: Callable[..., Any],
    mutant: Callable[..., Any],
    *,
    seed: int,
    maximum: int,
    random_cases: int,
) -> JsonDict:
    cm = mm = comparisons = 0
    fc = fm = None
    for tax_before, relief in _housing_pairs(seed, maximum, random_cases):
        lookup = _Lookup(
            {
                "taxe_habitation_commune_epci_avant_degrevement": tax_before,
                "degrevement_plafonnement_taxe_habitation": relief,
            }
        )
        external = method(lookup, object(), object())
        inputs = {"tax_before_relief": tax_before, "relief": relief}
        comparisons += 1
        cm, fc = _compare(external, adapter(tax_before, relief), inputs, cm, fc)
        mm, fm = _compare(external, mutant(tax_before, relief), inputs, mm, fm)
    return {
        "comparisons": comparisons,
        "correct_mismatches": cm,
        "mutant_mismatches": mm,
        "first_correct_mismatch": fc,
        "first_mutant_mismatch": fm,
    }


def _run_oscar_partial(
    method: Callable[..., Any],
    adapter: Callable[..., Any],
    mutant: Callable[..., Any],
    *,
    num_min: int,
    num_max: int,
    required_min: int,
    required_max: int,
) -> JsonDict:
    cm = mm = comparisons = 0
    fc = fm = None
    for num in range(num_min, num_max + 1):
        for req in range(required_min, required_max + 1):
            external = method(_PartialSelf(value=req, num_matches=num), object(), object())
            inputs = {"num_matches": num, "required_count": req}
            comparisons += 1
            cm, fc = _compare(external, adapter(num, req), inputs, cm, fc)
            mm, fm = _compare(external, mutant(num, req), inputs, mm, fm)
    return {
        "comparisons": comparisons,
        "correct_mismatches": cm,
        "mutant_mismatches": mm,
        "first_correct_mismatch": fc,
        "first_mutant_mismatch": fm,
    }


def _run_oscar_satisfied(
    method: Callable[..., Any],
    adapter: Callable[..., Any],
    mutant: Callable[..., Any],
    *,
    num_min: int,
    num_max: int,
    required_min: int,
    required_max: int,
) -> JsonDict:
    cm = mm = comparisons = 0
    fc = fm = None
    offer = object()
    for num in range(num_min, num_max + 1):
        for req in range(required_min, required_max + 1):
            correct = adapter(num, req)
            wrong = mutant(num, req)
            for partition in _partitions(num):
                lines = [_Line(q) for q in partition]
                lines.append(_Line(7, applicable=False))
                external = method(_SatisfiedSelf(req), offer, _Basket(lines))
                inputs = {"num_matches": num, "required_count": req, "partition": partition}
                comparisons += 1
                cm, fc = _compare(external, correct, inputs, cm, fc)
                mm, fm = _compare(external, wrong, inputs, mm, fm)
    return {
        "comparisons": comparisons,
        "correct_mismatches": cm,
        "mutant_mismatches": mm,
        "first_correct_mismatch": fc,
        "first_mutant_mismatch": fm,
    }


def run_preservation(
    *, catalog_path: Path, lock_path: Path, external_root: Path, repo_root: Path, output_dir: Path
) -> JsonDict:
    catalog = _load_json(catalog_path)
    lock = _load_json(lock_path)
    locked = {str(x["id"]): x for x in lock["sources"] if isinstance(x, dict)}
    rules = catalog["rules"]
    seed = int(catalog["seed"])
    details = []
    failures = []
    total = 0
    started = time.perf_counter()

    for raw in rules:
        rule = dict(raw)
        rid = str(rule["id"])
        sid = str(rule["source_id"])
        repo = external_root / sid
        try:
            expected = str(rule["resolved_commit"])
            if not (expected == str(locked[sid]["resolved_commit"]) == _checkout_commit(repo)):
                raise ValueError("locked/catalog/checkout commit mismatch")

            external_path = repo / str(rule["external_source"])
            adapter_path = repo_root / str(rule["adapter"])
            ns = {}
            harness = str(rule["harness"])
            if harness == "OPENFISCA_BOOLEAN_LOOKUP":
                ns["not_"] = lambda value: not value
            elif harness == "OPENFISCA_CLAMPED_SUBTRACTION":
                ns["max_"] = max

            extracted = _extract_method(
                external_path,
                class_name=str(rule["external_class"]),
                method_name=str(rule["external_method"]),
                namespace=ns,
            )
            module = _load_module(adapter_path)
            adapter = getattr(module, str(rule["adapter_function"]))
            mutant = getattr(module, str(rule["mutant_function"]))
            domain = dict(rule["validation_domain"])

            if harness == "OPENFISCA_BOOLEAN_LOOKUP":
                result = _run_apprenticeship(extracted.function, adapter, mutant)
            elif harness == "OPENFISCA_CLAMPED_SUBTRACTION":
                result = _run_housing(
                    extracted.function,
                    adapter,
                    mutant,
                    seed=seed,
                    maximum=int(domain["max"]),
                    random_cases=int(domain["random_cases"]),
                )
            elif harness == "OSCAR_POST_AGGREGATION_PARTIAL":
                result = _run_oscar_partial(
                    extracted.function,
                    adapter,
                    mutant,
                    num_min=int(domain["num_matches_min"]),
                    num_max=int(domain["num_matches_max"]),
                    required_min=int(domain["required_count_min"]),
                    required_max=int(domain["required_count_max"]),
                )
            elif harness == "OSCAR_CONTROLLED_BASKET_THRESHOLD":
                result = _run_oscar_satisfied(
                    extracted.function,
                    adapter,
                    mutant,
                    num_min=int(domain["num_matches_min"]),
                    num_max=int(domain["num_matches_max"]),
                    required_min=int(domain["required_count_min"]),
                    required_max=int(domain["required_count_max"]),
                )
            else:
                raise ValueError(f"unknown harness: {harness}")

            total += int(result["comparisons"])
            passed = result["correct_mismatches"] == 0 and result["mutant_mismatches"] > 0
            details.append(
                {
                    "rule_id": rid,
                    "source_id": sid,
                    "resolved_commit": expected,
                    "external_source": str(rule["external_source"]),
                    "external_class": str(rule["external_class"]),
                    "external_method": str(rule["external_method"]),
                    "external_source_sha256": extracted.source_sha256,
                    "external_method_sha256": extracted.method_sha256,
                    "external_method_lines": {
                        "start": extracted.line_start,
                        "end": extracted.line_end,
                    },
                    "adapter": str(rule["adapter"]),
                    "adapter_sha256": _sha256_file(adapter_path),
                    "adapter_function": str(rule["adapter_function"]),
                    "mutant_function": str(rule["mutant_function"]),
                    "harness": harness,
                    "validation_domain": domain,
                    **result,
                    "passed": passed,
                }
            )
        except (KeyError, OSError, TypeError, ValueError, AttributeError) as exc:
            failures.append({"rule_id": rid, "error": f"{type(exc).__name__}: {exc}"})

    correct_mismatches = sum(int(x["correct_mismatches"]) for x in details)
    mutant_mismatches = sum(int(x["mutant_mismatches"]) for x in details)
    rules_passed = sum(1 for x in details if x["passed"])
    passed = (
        not failures
        and len(details) == len(rules)
        and rules_passed == len(rules)
        and correct_mismatches == 0
        and mutant_mismatches > 0
    )

    summary = {
        "benchmark_version": "0.8.0",
        "claim_scope": catalog["claim_scope"],
        "seed": seed,
        "rules_configured": len(rules),
        "rules_checked": len(details),
        "rules_passed": rules_passed,
        "total_comparisons": total,
        "correct_adapter_mismatches": correct_mismatches,
        "mutant_mismatches": mutant_mismatches,
        "failures": failures,
        "runtime_seconds": time.perf_counter() - started,
        "passed": passed,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "details.json").write_text(
        json.dumps(details, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", type=Path, default=Path("benchmarks/v0.8/catalog.json"))
    p.add_argument("--lock", type=Path, default=Path("benchmarks/v0.6/LOCK.json"))
    p.add_argument("--external-root", type=Path, default=Path("external_sources/v0.6"))
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--output-dir", type=Path, default=Path("benchmarks/v0.8/results"))
    a = p.parse_args()
    s = run_preservation(
        catalog_path=a.catalog,
        lock_path=a.lock,
        external_root=a.external_root,
        repo_root=a.repo_root,
        output_dir=a.output_dir,
    )
    print("BIZPROOF V0.8 source-executed adapter preservation")
    print(f"Rules passed: {s['rules_passed']}/{s['rules_configured']}")
    print(f"Comparisons: {s['total_comparisons']}")
    print(f"Correct-adapter mismatches: {s['correct_adapter_mismatches']}")
    print(f"Mutant mismatches: {s['mutant_mismatches']}")
    print(f"Failures: {len(s['failures'])}")
    print(f"Runtime seconds: {s['runtime_seconds']:.6f}")
    print("PASS" if s["passed"] else "FAIL")
    return 0 if s["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
