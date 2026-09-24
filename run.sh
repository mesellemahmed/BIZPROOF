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
EOF
    ;;
esac
