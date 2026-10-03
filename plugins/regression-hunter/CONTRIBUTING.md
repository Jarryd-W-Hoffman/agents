# Contributing to regression-hunter

Repository-wide conventions are in the root [CONTRIBUTING.md](../../CONTRIBUTING.md). Paths here are relative to `plugins/regression-hunter/`.

## The invariants

1. **Read-only.** The reviewer never edits a file, runs the application or checks out another revision. Keep `disallowedTools` and the guard.
2. **No history, no agent.** The skill runs the scan first and stops when `analyse` is false.
3. **Every finding names an earlier commit.** A defect with no history behind it is another plugin's job; keeping this rule is what stops regression-hunter becoming a second correctness reviewer.

## Teaching the scan

- **What counts as a fix:** `FIX_RE` in `skills/hunt/scripts/history-scan.py`. Add a word only with a case in `Classify` in `tests/test_history_scan.py`, including one that must not match.
- **Thresholds** (`PARTNER_MIN`, `PARTNER_RATIO`, depths and caps) are at the top of the script. Change them with a test that shows why.

## Evals

A case is a commit history. Add `evals/fixtures/<name>/commits/NN-slug/` directories (each a `MESSAGE` plus files; `DELETE` lists removals), a `head/` overlay and `INTENT.md`; add the case to `CASES` in `evals/build_prompts.py` and write `evals/<case>/graders/criteria.md`; then run `python3 evals/build_prompts.py`. Keep every maintainer note on an `EVAL:` line.

## Shared files

`skills/hunt/scripts/finding.schema.json`, `finding_contract.py` and everything under `hooks/` except `hooks.json` are copies. Edit the canonical files and run `python3 ../../scripts/sync-shared.py --write`.

## Before opening a PR

```bash
../../scripts/check.sh regression-hunter
```
