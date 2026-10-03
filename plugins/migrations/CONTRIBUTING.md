# Contributing to migrations

Repository-wide conventions (layout, the check script, shared code, adding a plugin) are in the root [CONTRIBUTING.md](../../CONTRIBUTING.md). Everything here is specific to this plugin, and every path is relative to `plugins/migrations/`.

## The three invariants

1. **Read-only.** The reviewer never edits a file, runs a migration or touches a database. Keep `disallowedTools` on the agent and the guard in `hooks/hooks.json`. Never add a database client, framework CLI or `--pretend` to anything the reviewer may run.
2. **No migrations, no agent.** The skill runs `find-migrations.py` before it launches anything and stops when the list is empty. That early stop is the plugin's cost model; `tests/test_skill_invariants.py` pins it.
3. **The finding contract.** `findings.json` follows `skills/check/scripts/finding.schema.json` with `pass` set to `migrations` and `MIG-` IDs, and is validated before it is mentioned.

## Shared files

`skills/check/scripts/finding.schema.json`, `finding_contract.py` and everything under `hooks/` except `hooks.json` are copies. Do not edit them here: edit the canonical file (`shared/finding-contract/` for the contract, `plugins/fourpass/hooks/` for the guard) and run `python3 ../../scripts/sync-shared.py --write`. CI fails on a copy edited in place.

## Teaching the detector a layout

Add a `(framework, pattern)` pair to `MIGRATION_RULES` in `skills/check/scripts/find-migrations.py`, in order: more specific layouts first. If its filenames carry a sortable version, add it to `VERSION_RES` so out-of-order detection covers it. Add the path to `FrameworkOf.CASES` in `tests/test_find_migrations.py`, and a non-migration path that must not match to `test_not_migrations`.

## Changing what the reviewer looks for

- Add the check to "What counts as a finding" in `agents/migration-reviewer.md` only when it can name a specific statement and a specific consequence. Generic database advice makes the reviewer noisy.
- Every new kind of finding wants a recall case and, where a safe version looks the same, a precision case: a fixture under `evals/fixtures/<name>/` with `INTENT.md`, `base/` and `head/`, a line in `CASES` in `evals/build_prompts.py`, and `evals/<case>/graders/criteria.md`. Then run `python3 evals/build_prompts.py`.
- Keep the shared sections ("External tooling (read-only)", "Untrusted input", "Confidence scoring") worded as in fourpass's agents, so the two plugins mean the same thing by the same number.

## Style

- Second person, imperative. `##` headings.
- Laravel examples first; database concepts stated so they hold for any framework.
- No emojis. No filler.

## Before opening a PR

```bash
../../scripts/check.sh migrations
```

Then load the plugin in a session and confirm the agent and skill appear:

```bash
claude --plugin-dir . -p "List the agent types and skills provided by the migrations plugin." --max-turns 1
```

Add an entry under `[Unreleased]` in `CHANGELOG.md` and bump `version` in `.claude-plugin/plugin.json` on release.
