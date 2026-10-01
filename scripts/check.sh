#!/usr/bin/env bash
# Every check this repo runs, in one place.
#
# CONTRIBUTING.md, the pull-request template and CI all used to carry their own
# copy of this list, and they had already drifted apart. They now all call this.
# Add a check here and everywhere picks it up.
#
# The repo is a marketplace of plugins, one per directory under plugins/. The
# marketplace manifest is validated once; everything else runs per plugin,
# from inside that plugin's directory, so each plugin stays self-contained and
# its tests never reach outside it.
#
#   ./scripts/check.sh                       everything, every plugin
#   ./scripts/check.sh --manifests           only manifest/component validation (needs `claude`)
#   ./scripts/check.sh --tests               only the Python suites (needs `python3`)
#   ./scripts/check.sh [--tests] four-pass-review   one plugin
#
# Exits non-zero on the first failure.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"

PYTHON="${PYTHON:-python3}"

what=all
only=""
for arg in "$@"; do
  case "$arg" in
    --manifests|--tests) what="$arg" ;;
    -*) echo "usage: $0 [--manifests|--tests] [plugin]" >&2; exit 2 ;;
    *) only="$arg" ;;
  esac
done

run() {
  printf '\n\033[1m==> [%s] %s\033[0m\n' "${PLUGIN:-marketplace}" "$*"
  "$@"
}

have_claude() {
  if command -v claude >/dev/null 2>&1; then return 0; fi
  echo "skipping manifest validation: \`claude\` is not on PATH" >&2
  return 1
}

plugins() {
  if [ -n "$only" ]; then
    [ -d "plugins/$only" ] || { echo "no such plugin: plugins/$only" >&2; exit 2; }
    echo "$only"
    return
  fi
  for d in plugins/*/; do
    [ -f "$d/.claude-plugin/plugin.json" ] && basename "$d"
  done
}

marketplace_manifest() {
  have_claude || return 0
  [ -n "$only" ] && return 0
  run claude plugin validate --strict .
}

plugin_manifests() {
  have_claude || return 0
  run claude plugin validate --strict .
  [ -d agents ] && run claude plugin validate --strict agents
  [ -d skills ] && run claude plugin validate --strict skills
  return 0
}

plugin_tests() {
  # Every tests/test_*.py except the opt-in integration suite, which needs
  # network and credentials and is run by hand (see the plugin's CONTRIBUTING).
  for t in tests/test_*.py; do
    case "$t" in *_integration.py) continue ;; esac
    run "$PYTHON" "$t"
  done
  # Each guard hook carries a --selftest that checks its scoping end to end.
  if [ -f hooks/readonly-guard.py ]; then
    run env READONLY_GUARD_AGENTS='*-reviewer' "$PYTHON" hooks/readonly-guard.py --selftest
  fi
  if [ -f hooks/test-scope-guard.py ]; then
    run env TEST_SCOPE_GUARD_AGENTS='*test-writer' "$PYTHON" hooks/test-scope-guard.py --selftest
  fi
}

for_each_plugin() {
  for PLUGIN in $(plugins); do
    export PLUGIN
    ( cd "$ROOT/plugins/$PLUGIN" && "$@" )
  done
}

case "$what" in
  all)         marketplace_manifest; for_each_plugin plugin_manifests; for_each_plugin plugin_tests ;;
  --manifests) marketplace_manifest; for_each_plugin plugin_manifests ;;
  --tests)     for_each_plugin plugin_tests ;;
esac

printf '\n\033[1mall checks passed\033[0m\n'
