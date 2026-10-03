# engineering-review

A Claude Code plugin that works out which of this marketplace's plugins a change needs, runs them in parallel, and merges what they report into one result.

```text
/engineering-review:review                 # plan and run, on the working tree
/engineering-review:review 214             # pull request #214
/engineering-review:review main...feature/x
/engineering-review:review 214 --plan      # show the plan only; runs nothing
```

```markdown
# Engineering review plan: PR #214: Add currency to orders

**Changed:** 3 files (4e1c2a9 → 9b7f310)
**Would run:** 3 plugin(s), in parallel · 4 reviewer agents + 1 reviewer agent + 1 analyst agent

## Would run

| Plugin | Kind | Output | Why | Cost |
|---|---|---|---|---|
| `four-pass-review` | review | findings.json | 2 file(s): `app/Models/Order.php`, `database/migrations/2026_10_01_000000_add_currency.php` | 4 reviewer agents, plus up to 6 lightweight verifiers |
| `migration-safety` | review | findings.json | 1 file(s): `database/migrations/2026_10_01_000000_add_currency.php` | 1 reviewer agent |
| `change-impact` | map | impact.json | 2 file(s): `app/Models/Order.php`, … | 1 analyst agent |

## Afterwards, if you want it

- `test-gap-writer` — Writes tests that prove correctness and completeness findings. Edits test files, so it is offered after the review and never run without asking. Offered after four-pass-review.
```

## How it runs

1. **Plan**, as below, and show it. With `--plan`, stop here.
2. **Run** each selected, installed plugin in its own `general-purpose` subagent, all launched in one message. Each subagent invokes that plugin's skill with the user's target and nothing else, so the plugin runs exactly as it does alone, including the agents it launches itself: four-pass-review's four reviewers, migration-safety's reviewer, change-impact's analyst. Total time is the slowest plugin's, not the sum.
3. **Merge** with `skills/review/scripts/merge.py`, by rules:
   - each plugin's `findings.json` must satisfy the [finding contract](../../shared/finding-contract/README.md), and its IDs must use the prefixes the registry gives that plugin; otherwise that plugin counts as failed;
   - findings are kept as each plugin wrote them, never combined; findings from different plugins on overlapping lines are listed as overlaps for a person to judge;
   - the verdict is computed from the merged findings, unless any selected plugin did not report (not installed, failed, no usable reply), which makes it `INCOMPLETE`. A review that did not happen is never a clean one.
4. **Report** one merged report with every finding under its original ID, and save `report.md` and a merged `findings.json`. test-gap-writer is offered with that file; it edits test files, so it is never run without asking.

Posting to a pull request is not part of it yet; each plugin is run without `--comment`.

### What it has been checked against

An end-to-end run on a throwaway Laravel repository (migration-safety's dropped-column fixture, as uncommitted changes) with all plugins loaded and Bash allowed only as `Bash(git:*)`, `Bash(python3:*)`, `Bash(mktemp:*)` and `Bash(gh:*)`. The first run found two bugs, both fixed: four-pass-review's launch-time preamble was refused under that permission, so its skill never loaded; and a plugin whose `report.md` could not be saved was counted as failed, dropping a valid critical finding from the merge. (Claude Code's Write tool refuses report files from subagents, so plugins run this way usually save only their JSON; that is expected and shows as a note.) The second run reported all three plugins and returned FAIL on migration-safety's critical MIG-1, for about $2.40 API-equivalent. It also showed that subagents share the session's scratchpad, where plugins save files with the same names, so each runner now makes its own directory. There is no `claude plugin eval` suite for running yet: an eval workspace has no repository for the plugins to resolve a target against.

## How it decides

No model. `skills/review/scripts/plan.py` takes the changed files (including untracked ones) and applies each plugin's path patterns from `skills/review/registry.json`:

- A plugin is **selected** when at least one changed file matches one of its `include` patterns and none of its `exclude` patterns.
- A **follow-up** such as test-gap-writer is never selected. It edits files, so it is offered after a plugin named in its `after` list has run.
- Each plugin's patterns mirror its own early stop. migration-safety is selected for migration paths only; change-impact skips docs, tests, lockfiles and assets; four-pass-review skips docs, lockfiles and assets. The plan does not select a plugin that would then stop without doing anything.

So the same change always gets the same plan, and the plan costs nothing. It also means selection is tested exactly rather than sampled: `tests/test_plan.py` has a table of 20 change shapes (docs only, tests only, a Laravel or Rails or Django or Alembic or Flyway or Prisma migration, a file merely named like a migration, a migrations package marker) and the plugins each must select. That table is this plugin's eval suite, and it runs in CI for free.

## Adding a plugin to the registry

Every plugin in the marketplace needs an entry; `scripts/check-registry.py` fails CI otherwise, and also checks that the entry's skill exists and that its finding prefixes match the [finding contract](../../shared/finding-contract/README.md)'s table. An entry is:

| Field | Meaning |
|---|---|
| `name`, `skill` | The plugin, and the skill to run, namespaced: `migration-safety:check`. |
| `kind` | `review` (writes findings), `map` (writes facts), or `follow-up` (offered afterwards, never selected). |
| `output` | `findings`, `impact` or `tests`. |
| `prefixes` | The finding ID prefixes it owns. |
| `cost`, `summary` | One line each, shown in the plan. |
| `include`, `exclude` | Globs over repository-relative paths. `*` stays within a segment, `**` crosses segments, and a pattern with no slash matches the file name anywhere. |
| `after` | For a follow-up: which plugins it follows. |

Add a row or two for the new plugin to `CASES` in `tests/test_plan.py`, at least one that selects it and one that skips it; `test_cases_exercise_every_selectable_plugin_both_ways` fails otherwise.

## Installation

```bash
claude --plugin-dir /path/to/agents/plugins/engineering-review
```

```text
/plugin marketplace add /path/to/agents
/plugin install engineering-review@jarrydh-agents
```

The plan marks any selected plugin that is not installed, with its install command, and the run records it as not run, which makes the verdict `INCOMPLETE`.

## Layout

```text
.claude-plugin/plugin.json
skills/review/
  SKILL.md                 the lead: plan, run in parallel, merge, report
  registry.json            every plugin, and the paths that select it
  references/
    plan-template.md       the plan
    runner-brief.md        what each plugin's subagent is told, and the reply it gives
    report-template.md     the merged report
  scripts/
    plan.py                selection, no model
    merge.py               the merge and the verdict, no model
    finding.schema.json    the finding contract
    finding_contract.py    its validator; both are copies of shared/finding-contract/
tests/
  test_plan.py             the selection table, the globs, the registry, the CLI
  test_merge.py            the merge rules and the verdict
  test_skill_invariants.py the script selects, the merge decides, plugins run unmodified
  test_lint.py             standard-library lint
```

## Development

```bash
../../scripts/check.sh engineering-review
python3 skills/review/scripts/plan.py --files database/migrations/2026_10_01_000000_x.php README.md
```
