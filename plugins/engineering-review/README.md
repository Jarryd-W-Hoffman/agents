# engineering-review

A Claude Code plugin that works out which of this marketplace's plugins a change needs, and shows the plan.

```text
/engineering-review:review --plan          # the working tree
/engineering-review:review 214 --plan      # pull request #214
/engineering-review:review main...feature/x --plan
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

**This version plans; it runs nothing.** Running the selected plugins in parallel and merging their results is the next step. The plan comes first because it settles the part every later plugin plugs into: the registry.

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

The plan marks any selected plugin that is not installed, with its install command. When running is built, a plugin that is not installed will be reported as not run, never as a clean result.

## Layout

```text
.claude-plugin/plugin.json
skills/review/
  SKILL.md                 the lead: resolve the target, run plan.py, show the plan
  registry.json            every plugin, and the paths that select it
  references/plan-template.md
  scripts/plan.py          selection, no model
tests/
  test_plan.py             the selection table, the globs, the registry, the CLI
  test_skill_invariants.py no agents, no writes, the script decides
  test_lint.py             standard-library lint
```

## Development

```bash
../../scripts/check.sh engineering-review
python3 skills/review/scripts/plan.py --files database/migrations/2026_10_01_000000_x.php README.md
```
