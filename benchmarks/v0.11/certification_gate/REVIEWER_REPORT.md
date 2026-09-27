# BIZPROOF V0.11 Certification Engine Safety Audit

This phase inventories the exact proof/certification implementation before V0.11 semantic contracts reuse it.

- `_reviewer_report` definitions: 2
- `_sha256_file` definitions: 3
- `_sha256_file` callsites: 8
- discovered proof-related functions: 20
- relevant tests: 13

## `_reviewer_report`

File: `src/bizproof/certification_pipeline.py` line 69

```python
def _reviewer_report(summary: JsonDict, certificates: list[JsonDict]) -> str:
    lines = [
        "# BIZPROOF V0.10 Reviewer Certification Report",
        "",
        "## Scope",
        "",
        str(summary["claim_scope"]),
        "",
        "## Global result",
        "",
        f"- Certificates configured: {summary['certificates_configured']}",
        f"- Certificates issued: {summary['certificates_issued']}",
        f"- Certificates failed: {summary['certificates_failed']}",
        f"- External systems: {summary['external_system_count']}",
        f"- V0.8 concrete comparisons represented: {summary['v08_total_comparisons']}",
        f"- V0.8 correct-adapter mismatches represented: {summary['v08_correct_mismatches']}",
        f"- V0.9 symbolic equivalences represented: {summary['v09_equivalences_proved']}",
        f"- Pipeline result: {'PASS' if summary['passed'] else 'FAIL'}",
        "",
        "## Certificates",
        "",
    ]

    for item in certificates:
        lines.extend(
            [
                f"### {item['certificate_id']}",
                "",
                f"- Status: **{item['status']}**",
                f"- Certification scope: `{item['certification_scope']}`",
                f"- External system: `{item['provenance']['source_id']}`",
                f"- Commit: `{item['provenance']['resolved_commit']}`",
                f"- Source: `{item['provenance']['external_source']}`",
                f"- Adapter: `{item['artifacts']['adapter_path']}`",
                f"- Contract: `{item['artifacts']['contract_path']}`",
                f"- V0.7: `{item['evidence']['v0.7']['correct_verdict']}`",
                (
                    f"- V0.8: {item['evidence']['v0.8']['comparisons']} comparisons, "
                    f"{item['evidence']['v0.8']['correct_mismatches']} correct mismatches"
                ),
                (
                    f"- V0.9: `{item['evidence']['v0.9']['correct_verdict']}` "
                    f"(`{item['evidence']['v0.9']['solver_status']}`)"
                ),
                f"- Certified symbolic slice: `{item['evidence']['v0.9']['external_slice']}`",
                f"- Certificate digest: `{item['certificate_digest']}`",
                "",
            ]
        )

        if item["failed_checks"]:
            lines.append("- Failed checks: " + ", ".join(item["failed_checks"]))
            lines.append("")

    return "\n".join(lines) + "\n"
```

File: `src/bizproof/generalization_feasibility.py` line 481

```python
def _reviewer_report(summary: JsonDict) -> str:
    lines = [
        "# BIZPROOF V0.11 Static Generalization Feasibility Census",
        "",
        "## Scope",
        "",
        (
            "This phase is a static feasibility assessment over the preregistered "
            "90-candidate cohort. Feasibility tiers are routing decisions for the "
            "next validation stage; they are NOT proof verdicts and are NOT "
            "certification outcomes."
        ),
        "",
        "## Cohort integrity",
        "",
        f"- Cohort SHA-256: `{summary['cohort_sha256']}`",
        f"- Candidates assessed: {summary['assessed_candidates']}",
        f"- Source mismatches: {summary['source_mismatches']}",
        f"- Extraction failures: {summary['extraction_failures']}",
        "",
        "## Unweighted cohort counts",
        "",
    ]

    for tier in FEASIBILITY_TIERS:
        lines.append(f"- `{tier}`: {summary['feasibility_counts'].get(tier, 0)}")

    lines.extend(
        [
            "",
            "## Weighted eligible-population estimates",
            "",
        ]
    )

    weighted = summary["weighted_estimates"]

    for tier in FEASIBILITY_TIERS:
        item = weighted[tier]
        lines.append(
            "- "
            f"`{tier}`: estimated rate {item['estimated_rate']:.4f}, "
            f"approx. 95% CI "
            f"[{item['approx_ci95_low']:.4f}, "
            f"{item['approx_ci95_high']:.4f}]"
        )

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "`F0`–`F3` describe the amount of semantic machinery expected "
                "before attempting V0.7/V0.8/V0.9 obligations. They must not be "
                "reported as CERTIFIED, PROVED, or DISPROVED."
            ),
            "",
        ]
    )

    return "\n".join(lines)
```

## `_sha256_file`

File: `src/bizproof/adapter_preservation.py` line 24

```python
def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())
```

File: `src/bizproof/certification_pipeline.py` line 22

```python
def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
```

File: `src/bizproof/symbolic_equivalence.py` line 24

```python
def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())
```

## `_sha256_file` callsites

File: `src/bizproof/adapter_preservation.py` line 36

```text
0031:         raise ValueError(f"expected JSON object: {path}")
0032:     return value
0033: 
0034: 
0035: def _load_module(path: Path) -> ModuleType:
0036:     name = f"_bizproof_adapter_{_sha256_file(path)[:16]}"
0037:     spec = importlib.util.spec_from_file_location(name, path)
0038:     if spec is None or spec.loader is None:
0039:         raise ValueError(f"cannot load adapter module: {path}")
0040:     module = importlib.util.module_from_spec(spec)
0041:     spec.loader.exec_module(module)
```

File: `src/bizproof/adapter_preservation.py` line 93

```text
0088:     segment = ast.get_source_segment(source, method_node) or ""
0089:     return ExtractedMethod(
0090:         function=execution_namespace[method_name],
0091:         line_start=method_node.lineno,
0092:         line_end=getattr(method_node, "end_lineno", method_node.lineno),
0093:         source_sha256=_sha256_file(path),
0094:         method_sha256=_sha256_bytes(segment.encode("utf-8")),
0095:     )
0096: 
0097: 
0098: def _checkout_commit(repo: Path) -> str:
```

File: `src/bizproof/adapter_preservation.py` line 469

```text
0464:                     "external_method_lines": {
0465:                         "start": extracted.line_start,
0466:                         "end": extracted.line_end,
0467:                     },
0468:                     "adapter": str(rule["adapter"]),
0469:                     "adapter_sha256": _sha256_file(adapter_path),
0470:                     "adapter_function": str(rule["adapter_function"]),
0471:                     "mutant_function": str(rule["mutant_function"]),
0472:                     "harness": harness,
0473:                     "validation_domain": domain,
0474:                     **result,
```

File: `src/bizproof/certification_pipeline.py` line 346

```text
0341:             checks,
0342:             "v0.9-mutant-witness",
0343:             str(d09["mutant"]["counterexample"]),
0344:         )
0345: 
0346:         external_sha = _sha256_file(external_path)
0347:         adapter_sha = _sha256_file(adapter_path)
0348:         contract_sha = _sha256_file(contract_path)
0349: 
0350:         _require(
0351:             str(d08["resolved_commit"]) == expected_commit,
```

File: `src/bizproof/certification_pipeline.py` line 347

```text
0342:             "v0.9-mutant-witness",
0343:             str(d09["mutant"]["counterexample"]),
0344:         )
0345: 
0346:         external_sha = _sha256_file(external_path)
0347:         adapter_sha = _sha256_file(adapter_path)
0348:         contract_sha = _sha256_file(contract_path)
0349: 
0350:         _require(
0351:             str(d08["resolved_commit"]) == expected_commit,
0352:             checks,
```

File: `src/bizproof/certification_pipeline.py` line 348

```text
0343:             str(d09["mutant"]["counterexample"]),
0344:         )
0345: 
0346:         external_sha = _sha256_file(external_path)
0347:         adapter_sha = _sha256_file(adapter_path)
0348:         contract_sha = _sha256_file(contract_path)
0349: 
0350:         _require(
0351:             str(d08["resolved_commit"]) == expected_commit,
0352:             checks,
0353:             "v0.8-commit-consistency",
```

File: `src/bizproof/symbolic_equivalence.py` line 410

```text
0405:     else:
0406:         raise ValueError(f"unsupported external mode: {mode}")
0407: 
0408:     metadata = {
0409:         "external_mode": mode,
0410:         "external_source_sha256": _sha256_file(external_path),
0411:         "external_method_sha256": _node_hash(source, method),
0412:         "external_slice_sha256": _node_hash(source, selected_node),
0413:         "external_method_lines": {
0414:             "start": method.lineno,
0415:             "end": getattr(method, "end_lineno", method.lineno),
```

File: `src/bizproof/symbolic_equivalence.py` line 439

```text
0434:     )
0435: 
0436:     expression = _compile_statements(function.body, context)
0437: 
0438:     return expression, {
0439:         "adapter_file_sha256": _sha256_file(path),
0440:         "adapter_function_sha256": _node_hash(source, function),
0441:         "adapter_function_lines": {
0442:             "start": function.lineno,
0443:             "end": getattr(function, "end_lineno", function.lineno),
0444:         },
```

## Scientific boundary

This is an implementation audit only. No V0.11 semantic contract or certification verdict is created.
