# Contributing to docs

Repository-wide conventions are in the root [CONTRIBUTING.md](../../CONTRIBUTING.md). Everything here is specific to this plugin; paths are relative to `plugins/docs/`.

## The three invariants

1. **Kite is the template.** `references/` is Kite's README and manual written down. When the user changes how Kite's docs look, change the references to match, and the checks in `scripts/docs_check.py` with them. `tests/test_skill_invariants.py` pins the parts that must not drift: the chapter's diagram, pseudocode and screenshot, and the README's sections.
2. **Real, confirmed, retakeable.** Nothing in a page is invented; every screenshot comes from `docs/screenshots.json` through `shoot.mjs`. A skill that starts drawing mock-ups or guessing defaults has broken the point of it.
3. **Writers are confined.** The `manual-writer` has no shell, and `hooks/docs-scope-guard.py` limits its writes to Markdown under `docs/`. Keep `disallowedTools` on the agent and the guard in `hooks/hooks.json`.

## Scripts

- `survey.py` and `docs_check.py` are Python, standard library only, 3.9 and up, like the rest of the repository.
- `shoot.mjs` is Node, because Playwright is. It has no dependencies of its own and loads Playwright from the project or `DOCS_PLAYWRIGHT_DIR`. Keep it that way: an install must not need `npm install` inside the plugin.

## Teaching it more

- **A stack:** add a `*_stack()` function to `survey.py` and to `STACKS`, with a test in `tests/test_survey.py`.
- **A check:** add it to `docs_check.py` as an error only if a reader would trip over it; template drift is a warning. Add a case to `tests/test_docs_check.py`, and run the check over Kite's docs to be sure it does not flag them.
- **A screenshot action:** add it to `ACTIONS` and `act()` in `shoot.mjs`, and to the list in `references/screenshots.md`.

## Checking screenshots by hand

The tests check the plan and the ANSI rendering without a browser. Before a release, take a real set:

```bash
mkdir -p /tmp/shoot && cd /tmp/shoot
printf '{"shots":[{"name":"t","out":"t.png","alt":"x","terminal":{"command":"ls --color=always"}},{"name":"p","out":"p.png","alt":"y","url":"data:text/html,<h1>ok</h1>"}]}' > plan.json
DOCS_PLAYWRIGHT_DIR=<a dir with playwright-core> node <path>/plugins/docs/scripts/shoot.mjs plan.json
```

and open both images.

## Before opening a PR

```bash
../../scripts/check.sh docs
claude --plugin-dir . -p "List the agent types and skills provided by the docs plugin." --max-turns 1
```

Add an entry under `[Unreleased]` in `CHANGELOG.md`.
