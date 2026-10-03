# Contributing to testgaps

Repository-wide conventions (layout, the check script, adding a plugin) are in the root [CONTRIBUTING.md](../../CONTRIBUTING.md). Everything here is specific to this plugin, and every path is relative to `plugins/testgaps/`.

## The one invariant

The writer adds tests and does nothing else. Every change to this plugin is judged against that:

- The agent's `tools:` may include `Edit` and `Write` and must not include `MultiEdit` or `NotebookEdit` (the guard covers them anyway, but there is no reason to grant them). Never grant network tools.
- The guard decides what a test path is and what a runner is. Widen either by adding to the tables in `hooks/test-scope-guard.py` and adding a test for the new case in `tests/test_test_scope_guard.py`. Never add a command that can write outside test paths, install anything, or send data.
- The skill's `allowed-tools` grants the lead `git` and `python3` for reading state and running the parser. The lead does not write tests and does not need `Edit`.
- The five outcomes (`REPRODUCED`, `COVERED`, `NOT_REPRODUCED`, `BLOCKED`, `NOT_WRITTEN`) are fixed. The skill tabulates them mechanically from the agent's output format, so a change to either side changes both, and `tests/test_skill_invariants.py` pins the vocabulary.

## Untrusted input

The writer reads a finding, a diff, PR text and code comments, all of which the change's author controls. They are evidence about what to test, never instruction to the writer. Keep the "Untrusted input" section in the agent and the matching rule in the skill; do not add a context source that treats fetched text as direction.

## The guard

`hooks/test-scope-guard.py` runs on every PreToolUse event while a `test-writer` agent is active (scoped by `TEST_SCOPE_GUARD_AGENTS` in `hooks/hooks.json`). It is a single file on purpose: it is a third the size of the sibling's read-only guard because its Bash policy is a positive allow-list rather than a classifier. When you change it:

- Keep it standard-library only, Python 3.9 compatible, and fail-closed.
- Keep the agent-identity detection and the fail-open-without-identity rule in step with the sibling's `readonly-guard.py`. They are copies, not imports: a plugin may not reach outside its directory.
- Add a test for every new allow or deny case and run `python3 tests/test_test_scope_guard.py`.
- After changing the scoping logic, run `TEST_SCOPE_GUARD_AGENTS='*test-writer' python3 hooks/test-scope-guard.py --selftest`.

## Style

- Second person, imperative. `##` headings. 140–220 lines for the agent file.
- Language-agnostic; give language-specific examples only as "e.g.".
- No emojis. No filler.

## Before opening a PR

```bash
../../scripts/check.sh testgaps
```

Then load the plugin in a session and confirm the agent and skill appear:

```bash
claude --plugin-dir . -p "List the agent types and skills provided by the testgaps plugin." --max-turns 1
```

Add an entry under `[Unreleased]` in `CHANGELOG.md` and bump `version` in `.claude-plugin/plugin.json` on release.
