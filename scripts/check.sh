#!/usr/bin/env bash
# Every check this repo runs, in one place.
#
# CONTRIBUTING.md, the pull-request template and CI all used to carry their own
# copy of this list, and they had already drifted apart. They now all call this.
# Add a check here and everywhere picks it up.
#
#   ./scripts/check.sh              everything
#   ./scripts/check.sh --manifests  only the manifest/component validation (needs `claude`)
#   ./scripts/check.sh --tests      only the Python suites (needs `python3`)
#
# Exits non-zero on the first failure.

set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
what="${1:-all}"

run() {
  printf '\n\033[1m==> %s\033[0m\n' "$*"
  "$@"
}

manifests() {
  if ! command -v claude >/dev/null 2>&1; then
    echo "skipping manifest validation: \`claude\` is not on PATH" >&2
    return 0
  fi
  run claude plugin validate --strict .
  run claude plugin validate --strict .claude-plugin/plugin.json
  run claude plugin validate --strict agents
  run claude plugin validate --strict skills
}

tests() {
  run "$PYTHON" tests/test_readonly_guard.py
  run env READONLY_GUARD_AGENTS='*-reviewer' "$PYTHON" hooks/readonly-guard.py --selftest
  run "$PYTHON" tests/test_post_review.py
  run "$PYTHON" tests/test_agent_consistency.py
  run "$PYTHON" tests/test_skill_invariants.py
  run "$PYTHON" tests/test_lint.py
  run "$PYTHON" tests/test_evals.py
}

case "$what" in
  all)        manifests; tests ;;
  --manifests) manifests ;;
  --tests)    tests ;;
  *) echo "usage: $0 [--manifests|--tests]" >&2; exit 2 ;;
esac

printf '\n\033[1mall checks passed\033[0m\n'
