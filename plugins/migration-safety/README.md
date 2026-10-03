# migration-safety

A Claude Code plugin that reviews database migrations for what breaks in production: the previous release running against the new schema during the deploy, statements that lock or rewrite large tables, data loss, constraints existing rows violate, edited migration history, and migrations that cannot be rolled back.

It costs nothing on a change with no migrations. A script finds the migrations first, and the reviewer agent is launched only when there are some.

| Piece | What it does |
|---|---|
| `check` skill | Resolves the target, finds the migrations, briefs one reviewer, writes the report and `findings.json`. |
| `migration-reviewer` agent | Reads the migrations, the schema before them, and the application code at the base **and** the head revision, and judges each statement against the deploy model. Read-only, enforced by a hook. |
| `find-migrations.py` | Finds migrations in a diff without a model: Laravel, Rails, Django, Alembic, Flyway, Prisma, plain SQL and Node layouts. Flags edited history and out-of-order timestamps. |

Laravel is the first-class case, with Laravel-specific checks such as `->change()` dropping unrestated modifiers from Laravel 11. The deploy-window, locking and constraint checks are about the database and apply to any framework.

## Installation

**Try it without installing** (loads for one session):

```bash
claude --plugin-dir /path/to/agents/plugins/migration-safety
```

**Install from this repo as a local marketplace:**

```text
/plugin marketplace add /path/to/agents
/plugin install migration-safety@jarrydh-agents
```

**Or copy the pieces into a project** (no namespace prefix), from this plugin's directory:

```bash
cd plugins/migration-safety
cp agents/migration-reviewer.md your-project/.claude/agents/
cp -r skills/check              your-project/.claude/skills/migration-check
cp -r hooks                     your-project/.claude/migration-safety-hooks/
```

Copying the pieces does not bring the read-only guard with them: it is registered by the plugin's `hooks.json`, which only the plugin install reads. Wire it up by hand as in [four-pass-review's README](../four-pass-review/README.md#external-tooling-strictly-read-only), with `READONLY_GUARD_AGENTS='*migration-reviewer'`.

## Usage

```text
/migration-safety:check                    # working tree against HEAD, including untracked migrations
/migration-safety:check 214                # pull request #214
/migration-safety:check main...feature/x   # a ref range
/migration-safety:check 214 --threshold 70
```

The agent can also be invoked on its own:

```text
Use the migration-reviewer agent on the migration I just wrote.
```

## The deploy model

Every migration has three audiences, and the reviewer asks the question for each:

1. **The old code** (the base revision), which keeps serving traffic while the migration runs and until the new release is switched in. Dropping a column it still reads is an outage for that window.
2. **The new code** (the head revision), which may start before or after the migration depending on the deploy.
3. **A fresh install**, which runs every migration from scratch. Editing a migration that has already run changes this and nothing else, so production and CI drift apart.

Unless told otherwise, the reviewer assumes the common zero-downtime shape (Envoyer, Deployer, Forge, rolling Kubernetes deploys): production data exists, migrations run while the previous release is live, and table sizes are unknown. It says in the report that it assumed this. A PASS against an assumed deploy model is weaker than one against a written one.

**Tell it how you deploy.** A few lines in the project's `CLAUDE.md`, or a file under `.claude/rules/`, make the review much sharper:

```markdown
## Database and deploys

- MySQL 8.0 on RDS. Deploys run `php artisan migrate --force` before the symlink switch (Envoyer).
- Large tables (millions of rows): `orders`, `order_items`, `events`, `audit_log`.
- Small lookup tables: `countries`, `currencies`, `plans`.
```

The reviewer reads rule files at the base revision, so a change cannot add the line that excuses it.

## Output

The report uses the same layout as four-pass-review's merged report, with `MIG-` finding IDs:

```markdown
# Migration safety: PR #214: Drop legacy email

**Verdict:** FAIL
**Migrations:** 1 (added 1) · laravel · 4e1c2a9 → 9b7f310
**Deploy model:** assumed default (no deploy config or rules found)
**Threshold:** 80

## Critical (1)

### [MIG-1] Drops legacy_email while the running release still reads and writes it
`database/migrations/2026_10_01_090000_drop_legacy_email_from_customers.php:12` · confidence 93 · migration-safety
Between the migration finishing and the new release going live, every customer page and every new customer returns a 500: the base CustomerController selects legacy_email and store() inserts it.
**Fix:** Ship the code change first; drop the column in the next release.
```

Every run that reviews something also saves `report.md` and `findings.json` to a temporary directory outside the repository. `findings.json` follows the repository's [finding contract](../../shared/finding-contract/README.md) with `pass` set to `migration-safety`, and is validated before the skill mentions it. Anything that reads findings, such as [test-gap-writer](../test-gap-writer/README.md), can take it as is. Most migration findings are about deploys rather than behaviour, so test-gap-writer will mark many of them `NOT_WRITTEN`; a broken `down()` or a backfill bug can be tested.

## Read-only, strictly

The reviewer never runs a migration, a seeder, `artisan`, a framework CLI or a database client, not even with `--pretend`: each needs a database connection, and a review must not touch one. Three layers enforce that, the same as four-pass-review's reviewers:

| Layer | Mechanism |
|---|---|
| Tool access | `disallowedTools: Edit, Write, MultiEdit, NotebookEdit` on the agent. |
| Guard hook | `hooks/readonly-guard.py`, scoped to `*migration-reviewer`. Denies file edits, state-changing commands (including `php artisan`, `mysql`, `psql`) and write-style MCP tools; auto-allows `git show`, `git grep`, `git ls-tree` and other reads. Fails closed. |
| Instructions | The agent prompt and the brief. |

The guard is a copy of four-pass-review's, kept identical by `scripts/sync-shared.py`. What it is and is not is in [SECURITY.md](../../SECURITY.md). Check it against the version you have:

```bash
READONLY_GUARD_AGENTS='*migration-reviewer' python3 hooks/readonly-guard.py --selftest
```

## Limits

- It reads code; it does not see the database. Table sizes, existing duplicates and NULLs are inferred from the code, the schema dump and your rule files. When they cannot be, the finding says so and its confidence reflects it.
- A migration in a layout `find-migrations.py` does not recognise is not reviewed. The skill says it found none. Add the layout to `MIGRATION_RULES` in the script, with a test.
- One reviewer and no verification pass, to keep the cost to one agent. Use `--threshold` to trade recall for precision.
- It does not post to a pull request yet. Copy the report, or feed `findings.json` to another tool.

## Layout

Everything below is relative to `plugins/migration-safety/`.

```text
.claude-plugin/
  plugin.json              plugin manifest
agents/
  migration-reviewer.md    the reviewer
skills/check/
  SKILL.md                 the lead
  references/
    reviewer-brief.md      the brief sent to the reviewer
    report-template.md     the report format
  scripts/
    find-migrations.py     finds migrations in a diff, no model
    finding.schema.json    the finding contract
    finding_contract.py    its validator; both are copies of shared/finding-contract/
hooks/
  hooks.json               registers the read-only guard for the reviewer
  readonly-guard.py        the guard; with guard/, a copy of four-pass-review's
  guard/
evals/                     claude plugin eval suite; see evals/README.md
tests/
  test_find_migrations.py  the detector
  test_skill_invariants.py read-only grants, guard scope, the early stop, the contract
  test_evals.py            the eval suite's own checks
  test_lint.py             standard-library lint
```

## Development

```bash
../../scripts/check.sh migration-safety            # everything CI runs for this plugin
python3 tests/test_find_migrations.py               # one suite
python3 evals/build_prompts.py                      # regenerate eval prompts after editing fixtures
```
