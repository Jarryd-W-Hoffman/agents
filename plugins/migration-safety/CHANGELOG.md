# Changelog

All notable changes to this plugin are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this plugin adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **The read-only guard (the copy of four-pass-review's) denies git options that run a command.** `git grep -O<cmd>` (`--open-files-in-pager`) and `--upload-pack` on `git fetch` and `git ls-remote` run the command they are given, and `git cat-file --filters` runs configured filters; all were auto-allowed as reads. Denied options are now also matched by prefix, because git accepts any unambiguous abbreviation of a long option: `git grep --textc`, `git fetch --for` and `git grep --open=<cmd>` got past the exact-name checks.

### Added

- `migration-reviewer` agent: judges a change's migrations against a production database that holds data and serves traffic while the previous release is still live. Reads the migrations, the schema before them, and the application code at both the base and the head revision. Reports old code breaking against the new schema, locks and rewrites on large tables, constraints existing rows violate, data loss (including Laravel 11's `->change()` dropping unrestated modifiers), edited or out-of-order migration history, backfills inside schema migrations, and missing or wrong `down()`. States the deploy model it judged against, and whether it was written down or assumed. Uses four-pass-review's confidence scale and output shape with `MIG-` IDs.
- `check` skill: resolves the working tree, a ref range or a PR; finds migrations with `scripts/find-migrations.py` and stops without launching anything when there are none; runs one reviewer; writes the report, and saves `report.md` and a validated `findings.json` in the shared finding contract.
- `scripts/find-migrations.py`: detects migrations for Laravel, Rails, Django, Alembic, Flyway, Prisma, plain SQL and Node layouts, including untracked files in the working tree; marks each as added, modified, deleted or renamed; flags added migrations dated before one already at base; lists schema dumps, deploy config and rule files at base.
- No launch-time preamble: the skill reads the repository state in Step 1. A preamble command that fails, as `git rev-parse HEAD` does in a repository with no commits, stops the skill from loading and leaves the model to improvise; every eval run did exactly that before this.
- The read-only guard, a copy of four-pass-review's kept identical by `scripts/sync-shared.py`, scoped to `*migration-reviewer`.
- `evals/`: four recall cases, two precision cases (one a matched pair with a recall case) and a no-migrations case, built from Laravel fixtures with a base and a head tree.
- Tests: the detector (including against a real git repository), skill invariants, the eval suite's own checks, and a standard-library lint pass.
