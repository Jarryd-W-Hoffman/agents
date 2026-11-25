#!/usr/bin/env bash
# Run a prompt in Claude Code, in a fresh demo repository, with every plugin in this
# marketplace loaded. The README's screenshots of real runs are taken with it:
#
#   docs/demo/run.sh "/review:plan"
#   docs/demo/run.sh "/migrations:check"
#
# The demo repository is rebuilt each time (see make-demo-repo.sh). Tools are allowed the
# way review's end-to-end run allows them: git, python3, mktemp, Write and Agent.
set -euo pipefail

here="$(cd "$(dirname "$0")/../.." && pwd)"
demo="$("$here/docs/demo/make-demo-repo.sh")"
dirs=()
for manifest in "$here"/plugins/*/.claude-plugin/plugin.json; do
  dirs+=(--plugin-dir "$(dirname "$(dirname "$manifest")")")
done
cd "$demo"
claude -p "$1" "${dirs[@]}" \
  --allowedTools "Bash(git:*)" "Bash(python3:*)" "Bash(mktemp:*)" "Write" "Agent" \
  2> >(grep -v "sign-in ends" >&2)
