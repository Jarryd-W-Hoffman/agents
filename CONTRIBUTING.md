# Contributing

This file covers the repository. Each plugin has its own `CONTRIBUTING.md` with the rules for its agents, hooks and skills; read that one too before touching a plugin.

## One directory per plugin

Every plugin lives under `plugins/<name>/` and is self-contained:

- `.claude-plugin/plugin.json` is its manifest and carries its own `version`.
- `agents/`, `skills/`, `hooks/` hold what the plugin ships. `${CLAUDE_PLUGIN_ROOT}` resolves to this directory at runtime, and an install copies only this directory, so nothing in a plugin may import, read or reference a file outside it. If two plugins need the same code, each carries its own copy.
- `tests/test_*.py` are its unit suites. Anything named `*_integration.py` is opt-in and not run by CI.
- `evals/` is its `claude plugin eval` suite, if it has one. Run from the plugin directory.
- `README.md`, `CHANGELOG.md` and `CONTRIBUTING.md` are its own.

The repository root holds what is shared: the marketplace manifest, `scripts/check.sh`, `SECURITY.md` and `.github/`.

## Adding a plugin

1. Create `plugins/<name>/` with a `.claude-plugin/plugin.json` and at least one of `agents/`, `skills/` or `hooks/`.
2. Add an entry to `.claude-plugin/marketplace.json` with `"source": "./plugins/<name>"`.
3. Add a row to the table in the root `README.md`.
4. Give it a `README.md`, a `CHANGELOG.md` starting at `[Unreleased]`, and tests under `tests/`.
5. Run `./scripts/check.sh <name>`. The script discovers plugins by their manifest, so no edit to it is needed.

## Before opening a PR

```bash
./scripts/check.sh
```

That runs, for every plugin: `claude plugin validate --strict` on the manifest and each component directory, every `tests/test_*.py`, and the read-only guard selftest where a plugin has one. CI runs the same script on Python 3.9 and 3.13, so if it passes locally it passes there. Add a new check to `scripts/check.sh` and everything picks it up.

Add an entry under `[Unreleased]` in the affected plugin's `CHANGELOG.md`. Plugins are versioned and released independently: bump `version` in that plugin's `plugin.json` on release and tag it `<name>-v<version>`.

## Style

- Python is standard library only and must run on 3.9.
- Second person, imperative. No emojis. No filler.
