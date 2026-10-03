# Eval suite

What this measures: whether the reviewer catches the migration defects that cause production incidents, whether it stays quiet on migrations that look dangerous and are not, and whether the skill launches no reviewer at all when there is nothing to review.

The harness, the cost model and the reasons for inlining fixtures are the same as four-pass-review's; read [its evals/README.md](../../four-pass-review/evals/README.md) first. What differs is below.

## Running it

From `plugins/migration-safety/`:

```bash
# one case, one run, while iterating
claude plugin eval --allow-tools Bash --ablation none --runs 1 \
  --case 'recall-dropped-column' --max-cost-usd 2.00 .

# the whole suite, one run each, no baseline arm
claude plugin eval --allow-tools Bash --ablation none --runs 1 .

# a baseline worth recording: 3 runs
claude plugin eval --allow-tools Bash --ablation none .
```

`--allow-tools Bash` needs Claude Code's sandbox, which on Linux needs `bubblewrap` and `socat` (`sudo apt install bubblewrap socat`). Without them every run is refused before it starts, reports `$0.00`, and scores 0, except that a precision grader with no guard against it would score an empty response 1. Both precision graders here score a missing report 0, and `tests/test_evals.py` pins that.

A run launches one reviewer, not four plus verifiers, so it costs a fraction of a four-pass run. `no-migrations` launches none and is the cheapest case in the repository. ## Baseline

Plugin 0.1.0, Claude Code 2.1.288, 2026-10-03, `--runs 1 --ablation none`: **7/7, $2.24 API-equivalent over 4 minutes** (three at a time).

| Case | Score | Cost | Seconds |
|---|---|---|---|
| no-migrations | 1 | $0.12 | 9 |
| precision-expand-contract | 1 | $0.30 | 126 |
| precision-new-table | 1 | $0.31 | 126 |
| recall-change-drops-nullable | 1 | $0.40 | 161 |
| recall-dropped-column | 1 | $0.37 | 64 |
| recall-edited-migration | 1 | $0.35 | 63 |
| recall-not-null-no-default | 1 | $0.39 | 75 |

Every run was checked in its trace: the skill loaded, the reviewer was launched in every case except `no-migrations` (no launch, as designed), and no sandbox error appeared. One run per case shows that each case *can* pass, not how often it does; record a `--runs 3` baseline before comparing changes against these numbers.

Two earlier attempts measured nothing and are not baselines. In the first, the eval sandbox could not start (Ubuntu's AppArmor user-namespace restriction), so every shell command failed. In the second, the skill's launch-time `git rev-parse --abbrev-ref HEAD` failed in the eval workspace's empty repository, which stops a skill loading; the model improvised from the prompt and still scored 5/7. That is why the skill now has no launch-time preamble, and why a score is only trusted after the trace shows the skill loaded.

## The cases

### Recall: does the reviewer catch a seeded defect?

Each fixture seeds one defect. The grader requires a `MIG-` finding at critical or major severity with the right failure scenario.

| Case | Fixture | Seeded defect |
|---|---|---|
| `recall-dropped-column` | `dropped-column` | Drops `customers.legacy_email` while the base release still selects and inserts it |
| `recall-not-null-no-default` | `not-null-no-default` | Adds `orders.currency` NOT NULL with no default; the base checkout inserts without it |
| `recall-change-drops-nullable` | `change-drops-nullable` | Laravel 11 `->change()` without restating `nullable()` makes `contacts.phone` NOT NULL |
| `recall-edited-migration` | `edited-migration` | Adds a column by editing a migration that already ran, so production never gets it |

### Precision: does it stay quiet when the migration is safe?

| Case | Fixture | The bait |
|---|---|---|
| `precision-expand-contract` | `expand-contract` | The same drop as `dropped-column`, but nothing at base uses the column any more |
| `precision-new-table` | `new-table` | Unique index, index and foreign key, all on a table created empty in the same migration |

Their graders score whether a critical or major false positive appears, not the verdict. A minor note that dropped data is gone is legitimate.

The two drop cases are a matched pair: the migration is identical, and only the base code differs. A reviewer that passes one and fails the other is reading the code. One that passes both or fails both is pattern-matching on `dropColumn`.

### Behaviour

| Case | Asserts |
|---|---|
| `no-migrations` | An empty `migrations` list stops the skill: no reviewer, no findings, no report. |

## Fixtures

Each fixture is `INTENT.md` plus two trees: `base/`, what production runs now, and `head/`, the change. `build_prompts.py` compares them to work out each file's status, runs the skill's own `find-migrations.py` logic over them for the packet, and inlines both trees into the prompt. The detector is therefore exercised by every case, and `tests/test_evals.py` fails if it stops recognising a fixture's migration.

Fixtures are plain PHP with no `vendor/` and nothing to install, because the reviewer only reads. `EVAL:` comment lines record the seeded defect or the bait and are stripped from the prompt; keep every such note on an `EVAL:` line.

**The prompts are generated. Do not edit `*/prompt.md` by hand.**

```bash
python3 evals/build_prompts.py           # regenerate from fixtures/
python3 evals/build_prompts.py --check   # fail if any prompt is stale
```

## What it does not measure

- Target resolution, PR fetching and running the detector against a real repository: the packet is pre-resolved, as in four-pass-review's suite. `tests/test_find_migrations.py` covers the detector against a real `git` repository, including untracked files.
- Judgement against a written deploy model: no fixture carries a rule file yet. A case where `CLAUDE.md` declares a table small, and the same lock risk on it must then not be reported, is the next one to add.
