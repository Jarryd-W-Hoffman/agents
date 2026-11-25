#!/usr/bin/env bash
# Build the throwaway repository the README's screenshots are taken in, and print its path.
#
# It is the migrations plugin's dropped-column eval fixture: a small Laravel app whose base
# revision is committed, with the change (drop customers.legacy_email) left uncommitted in
# the working tree, the way a change looks before you open a pull request. Eval hints are removed.
#
#   docs/demo/make-demo-repo.sh [dir]     default: ${TMPDIR:-/tmp}/agents-demo
set -euo pipefail

here="$(cd "$(dirname "$0")/../.." && pwd)"
fixture="$here/plugins/migrations/evals/fixtures/dropped-column"
dir="${1:-${TMPDIR:-/tmp}/agents-demo}"

rm -rf "$dir"
mkdir -p "$dir"
cp -R "$fixture/base/." "$dir/"
git -C "$dir" init -q -b main
git -C "$dir" add -A
git -C "$dir" -c user.name=Demo -c user.email=demo@example.com commit -q -m "Customers with a legacy email"
cp -R "$fixture/head/." "$dir/"
# `EVAL:` comments tell eval graders where the seeded defect is; a demo should not carry them.
grep -rl "EVAL:" "$dir" --exclude-dir=.git | while read -r f; do
  grep -v "EVAL:" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done
echo "$dir"
