# Eval suite

What this measures: whether the reviewer catches a change that undoes an earlier fix or revert, whether it stays quiet when a change near an old fix keeps the fix's invariant, and whether the skill launches nothing when the history has nothing to say.

Harness, cost model and the reasons for inlining are as in [fourpass's evals/README.md](../../fourpass/evals/README.md). `--allow-tools Bash` needs Claude Code's sandbox (`bubblewrap` and `socat` on Linux, and on Ubuntu the `bwrap-userns-restrict` AppArmor profile unloaded); without it every run is refused, and a run whose skill did not load measures the base model, not the plugin.

```bash
# from plugins/regressions/
claude plugin eval --allow-tools Bash --ablation none --runs 1 .
```

## The cases

| Case | Fixture | What it checks |
|---|---|---|
| `recall-revert-reintroduced` | `revert-reintroduced` | The change re-adds `Cache::tags`, which `fcacd17` reverted because the file cache store has no tags (INC-142), and the store is still `file` |
| `recall-fix-guard-removed` | `fix-guard-removed` | A refactor into `PaymentRecorder` drops the idempotency check `018c50a` added for double charges on retried webhooks (#311) |
| `precision-fix-guard-kept` | `fix-guard-kept` | The same refactor, with the check moved intact into `PaymentRecorder::record` |
| `nothing-in-history` | `quiet-history` | No fix or revert ever touched the changed lines: stop, launch nothing |

The two webhook cases are a matched pair: identical history, identical scan output (`tests/test_evals.py` checks that), different head. Passing both means the reviewer read the code; passing one means it pattern-matched on "a fix touched these lines".

## Fixtures are histories

Each fixture is a sequence of commits (`commits/NN-slug/` with a `MESSAGE` and the files it changes), a `head/` overlay for the change under review, and `INTENT.md`. `repo_builder.py` commits them with a fixed author and fixed dates, so the same fixture always yields the same SHAs; `build_prompts.py` builds it, runs the skill's own `history-scan.py`, and inlines the scan, `git show` of every commit it lists, the diff and the changed files. A revert's message names the commit it reverts as `{{SHA:NN}}`. `EVAL:` lines are stripped from both the repository and the prompt.

**The prompts are generated. Do not edit `*/prompt.md` by hand.** `tests/test_evals.py` rebuilds every fixture and fails if a prompt is stale.

## Baseline

Plugin 0.1.0, Claude Code 2.1.288, 2026-10-03, `--runs 1 --ablation none`: **4/4, $1.36 API-equivalent** (plus a $0.17 probe of `nothing-in-history` first, which also passed).

| Case | Score | Cost | Seconds |
|---|---|---|---|
| nothing-in-history | 1 | $0.12 | 9 |
| precision-fix-guard-kept | 1 | $0.39 | 61 |
| recall-fix-guard-removed | 1 | $0.48 | 78 |
| recall-revert-reintroduced | 1 | $0.38 | 63 |

Every run was checked in its trace: the skill loaded, the reviewer was launched in every case except `nothing-in-history` (no launch, as designed), and no sandbox error appeared. Both halves of the matched pair passed. One run per case shows each case *can* pass; record a `--runs 3` baseline before comparing changes.
