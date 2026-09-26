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
  check)
    docker compose run --rm --entrypoint sh bizproof -lc \
      'ruff check . && ruff format --check . && mypy src && pytest'
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
EOF
    ;;
esac
