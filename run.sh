#!/usr/bin/env bash
set -euo pipefail

cmd="${1:-help}"

case "$cmd" in
  build)
    docker compose build
    ;;
  test)
    docker compose run --rm --entrypoint pytest bizproof
    ;;
  demo-enum)
    docker compose run --rm bizproof verify \
      --contract contracts/br_minor_account.yaml \
      --backend enum
    ;;
  demo-z3)
    docker compose run --rm bizproof verify \
      --contract contracts/br_minor_account.yaml \
      --backend z3
    ;;
  demo-vacuous)
    docker compose run --rm bizproof verify \
      --contract contracts/br_minor_account_vacuous.yaml \
      --backend z3
    ;;
  differential)
    docker compose run --rm bizproof differential \
      --contracts-dir contracts/differential
    ;;
  fuzz-differential)
    docker compose run --rm bizproof fuzz-differential \
      --cases 1000 \
      --seed 20260923 \
      --generated-dir experiments/generated/v0.2 \
      --report experiments/results/v0.2-differential-summary.json
    ;;
  baseline-comparison)
    docker compose run --rm --entrypoint python bizproof \
      -m bizproof.baseline_comparison \
      --catalog benchmarks/v0.3/catalog.json \
      --output experiments/results/v0.4-baseline-comparison-summary.json \
      --details experiments/results/v0.4-baseline-comparison-details.csv \
      --hypothesis-examples 100 \
      --crosshair-condition-timeout 0.5 \
      --crosshair-process-timeout 5.0
    ;;
  challenge-benchmark)
    docker compose run --rm --entrypoint python bizproof \
      -m bizproof.challenge_benchmark \
      --catalog benchmarks/v0.5/catalog.json \
      --output experiments/results/v0.5-challenge-summary.json
    ;;
  external-acquire)
    bash scripts/acquire_external_corpus.sh
    ;;
  external-audit)
    docker compose run --rm --entrypoint python bizproof \
      -m bizproof.external_corpus \
      --sources benchmarks/v0.6/sources.json \
      --lock benchmarks/v0.6/LOCK.json \
      --external-root external_sources/v0.6 \
      --output-dir benchmarks/v0.6/results
    ;;
  external-corpus)
    bash scripts/acquire_external_corpus.sh
    docker compose run --rm --entrypoint python bizproof \
      -m bizproof.external_corpus \
      --sources benchmarks/v0.6/sources.json \
      --lock benchmarks/v0.6/LOCK.json \
      --external-root external_sources/v0.6 \
      --output-dir benchmarks/v0.6/results
    ;;
  check)
    docker compose run --rm --entrypoint sh bizproof -lc \
      'ruff check . && ruff format --check . && mypy src && pytest'
    ;;
  external-semantic)
    docker compose run --rm --entrypoint python bizproof -m bizproof.external_semantic_validation --catalog benchmarks/v0.7/catalog.json --lock benchmarks/v0.6/LOCK.json --external-root external_sources/v0.6 --repo-root . --output-dir benchmarks/v0.7/results
    ;;
  adapter-preservation)
    docker compose run --rm --entrypoint python bizproof -m bizproof.adapter_preservation --catalog benchmarks/v0.8/catalog.json --lock benchmarks/v0.6/LOCK.json --external-root external_sources/v0.6 --repo-root . --output-dir benchmarks/v0.8/results
    ;;
  symbolic-equivalence)
    docker compose run --rm --entrypoint python bizproof -m bizproof.symbolic_equivalence --catalog benchmarks/v0.9/catalog.json --lock benchmarks/v0.6/LOCK.json --external-root external_sources/v0.6 --repo-root . --output-dir benchmarks/v0.9/results
    ;;
  certification-bundle)
    docker compose run --rm --entrypoint python bizproof -m bizproof.certification_pipeline --registry benchmarks/v0.10/registry.json --lock benchmarks/v0.6/LOCK.json --repo-root . --external-root external_sources/v0.6 --certificates-dir benchmarks/v0.10/certificates --results-dir benchmarks/v0.10/results
    ;;
  generalization-cohort)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_cohort --candidates benchmarks/v0.6/results/candidates.jsonl --registry benchmarks/v0.10/registry.json --output-dir benchmarks/v0.11/results
    ;;
  generalization-feasibility)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_feasibility --cohort benchmarks/v0.11/results/cohort.jsonl --cohort-summary benchmarks/v0.11/results/summary.json --lock benchmarks/v0.6/LOCK.json --external-root external_sources/v0.6 --output-dir benchmarks/v0.11/feasibility
    ;;
  generalization-symbolic-probe)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_symbolic_probe --assessment benchmarks/v0.11/feasibility/assessment.jsonl --cohort-summary benchmarks/v0.11/results/summary.json --lock benchmarks/v0.6/LOCK.json --external-root external_sources/v0.6 --output-dir benchmarks/v0.11/symbolic_probe
    ;;
  generalization-workplan)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_workplan --feasibility-summary benchmarks/v0.11/feasibility/summary.json --assessment benchmarks/v0.11/feasibility/assessment.jsonl --probe-summary benchmarks/v0.11/symbolic_probe/summary.json --probe benchmarks/v0.11/symbolic_probe/probe.jsonl --output-dir benchmarks/v0.11/workplan
    ;;
  generalization-families)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_families --feasibility-summary benchmarks/v0.11/feasibility/summary.json --assessment benchmarks/v0.11/feasibility/assessment.jsonl --probe-summary benchmarks/v0.11/symbolic_probe/summary.json --probe benchmarks/v0.11/symbolic_probe/probe.jsonl --workplan-summary benchmarks/v0.11/workplan/summary.json --queue benchmarks/v0.11/workplan/queue.jsonl --output-dir benchmarks/v0.11/families
    ;;
  generalization-contract-skeleton)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_contract_skeleton --probe-summary benchmarks/v0.11/symbolic_probe/summary.json --probe benchmarks/v0.11/symbolic_probe/probe.jsonl --workplan-summary benchmarks/v0.11/workplan/summary.json --queue benchmarks/v0.11/workplan/queue.jsonl --output-dir benchmarks/v0.11/contracts
    ;;
  generalization-semantic-evidence)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_semantic_evidence --contract-summary benchmarks/v0.11/contracts/summary.json --contract-skeletons benchmarks/v0.11/contracts/contract_skeletons.jsonl --binding-registry benchmarks/v0.11/contracts/binding_registry.json --lock benchmarks/v0.6/LOCK.json --external-root external_sources/v0.6 --output-dir benchmarks/v0.11/semantic_evidence
    ;;
  generalization-symbol-trace)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_symbol_trace --semantic-summary benchmarks/v0.11/semantic_evidence/summary.json --occurrence-evidence benchmarks/v0.11/semantic_evidence/occurrence_evidence.jsonl --semantic-registry benchmarks/v0.11/semantic_evidence/semantic_registry.json --lock benchmarks/v0.6/LOCK.json --external-root external_sources/v0.6 --output-dir benchmarks/v0.11/symbol_trace
    ;;
  generalization-contract-readiness)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_contract_readiness --symbol-summary benchmarks/v0.11/symbol_trace/summary.json --contract-candidates benchmarks/v0.11/symbol_trace/contract_candidates.json --occurrence-traces benchmarks/v0.11/symbol_trace/occurrence_traces.jsonl --output-dir benchmarks/v0.11/contract_readiness
    ;;
  generalization-name-resolution)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_name_resolution --contract-skeletons benchmarks/v0.11/contracts/contract_skeletons.jsonl --occurrence-evidence benchmarks/v0.11/semantic_evidence/occurrence_evidence.jsonl --semantic-registry benchmarks/v0.11/semantic_evidence/semantic_registry.json --previous-traces benchmarks/v0.11/symbol_trace/occurrence_traces.jsonl --lock benchmarks/v0.6/LOCK.json --external-root external_sources/v0.6 --output-dir benchmarks/v0.11/name_resolution
    ;;
  generalization-protocol-closure)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_protocol_closure --name-summary benchmarks/v0.11/name_resolution/summary.json --occurrence-resolution benchmarks/v0.11/name_resolution/occurrence_resolution.jsonl --contract-queue benchmarks/v0.11/name_resolution/contract_queue.json --external-root external_sources/v0.6 --output-dir benchmarks/v0.11/protocol_closure
    ;;
  generalization-certification-audit)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_certification_audit --repo-root . --output-dir benchmarks/v0.11/certification_gate
    ;;
  generalization-semantic-contract-batch)
    docker compose run --rm --entrypoint python bizproof -m bizproof.generalization_semantic_contract_batch --occurrences benchmarks/v0.11/name_resolution/occurrence_resolution.jsonl --protocols benchmarks/v0.11/protocol_closure/protocols.json --dependency-lock benchmarks/v0.11/semantic_contracts/openfisca_core_lock.json --external-root external_sources/v0.6 --dependency-source-root external_sources/v0.11/openfisca_core_44_0_4 --output-dir benchmarks/v0.11/semantic_contracts
    ;;
  generalization-semantic-contract-closure)
    docker compose run --rm -T --entrypoint sh bizproof -lc '
      rm -rf /tmp/bizproof-numpy &&
      python -m pip install --disable-pip-version-check --quiet --no-deps --require-hashes --target /tmp/bizproof-numpy -r benchmarks/v0.11/semantic_contract_closure/numpy_requirements.txt &&
      PYTHONPATH=/tmp/bizproof-numpy:/workspace/src python -m bizproof.generalization_semantic_contract_closure --phase-n-root benchmarks/v0.11/semantic_contracts --numpy-lock benchmarks/v0.11/semantic_contract_closure/numpy_lock.json --output-dir benchmarks/v0.11/semantic_contract_closure
    '
    ;;
  *)
    cat <<'EOF'
Usage:
  ./run.sh build
  ./run.sh test
  ./run.sh check
  ./run.sh demo-enum
  ./run.sh demo-z3
  ./run.sh demo-vacuous
  ./run.sh differential
  ./run.sh fuzz-differential
  ./run.sh baseline-comparison
  ./run.sh challenge-benchmark
  ./run.sh external-acquire
  ./run.sh external-audit
  ./run.sh external-corpus
  ./run.sh external-semantic
  ./run.sh adapter-preservation
  ./run.sh symbolic-equivalence
  ./run.sh certification-bundle
EOF
    ;;
esac
