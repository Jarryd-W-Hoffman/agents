---
name: screenshots
description: Retakes the screenshots a README and user manual use, from the plan in docs/screenshots.json, and adds shots to that plan. Starts the app with demo data (or uses one already running), runs the plugin's Playwright screenshot script, opens every image to check it, and reports which pages use each image. Use when the user asks to refresh, retake or add screenshots, after a UI change, or when docs_check reports a screenshot missing.
argument-hint: "[shot-name ...] [--add \"<what to show>\"] [--url <running app>]"
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git:*), Bash(python3:*), Bash(node:*), Bash(npm:*), Bash(npx:*), Bash(curl:*), Bash(ls:*), Bash(mkdir:*)
---

# Screenshots

Retake or add the docs' screenshots, following `${CLAUDE_PLUGIN_ROOT}/references/screenshots.md`. Read it first.

## Arguments

Arguments received: `$ARGUMENTS`

| Form | Meaning |
|---|---|
| *(empty)* | Retake every shot in `docs/screenshots.json`. |
| `graph search` | Retake only these shots, by name. |
| `--add "the export dialog"` | Add a shot for that to the plan, take it, and say where to use it. |
| `--url <url>` | The app is already running there; set `baseUrl` to it for this run. |

## Procedure

1. `git rev-parse --show-toplevel`; stop outside a repository. Read `docs/screenshots.json`. If there is none, say so and offer `/docs:readme` or `/docs:manual`, which create it; with `--add`, create it.
2. With `--add`, find the screen in the code (route, component, selector), and add a shot with a kebab-case name, an `out` (`docs/manual/images/` for the manual, `.github/screenshots/` for the README) and alt text.
3. `node "${CLAUDE_PLUGIN_ROOT}/scripts/shoot.mjs" docs/screenshots.json --check`.
4. Start the app with demo data, unless every selected shot is a terminal shot or `--url` was given. Then run `shoot.mjs` (with `--only` for named shots).
5. Open every image you took with Read. Retake any that shows a spinner, an error, a login page, an empty list or a half-drawn view; fix the plan (a `waitFor`, an action) rather than adding blind waits.
6. Stop the app.
7. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/docs_check.py" --root <toplevel> --readme README.md --manual docs/manual --plan docs/screenshots.json` (drop `--manual` if there is no manual) and fix image errors.
8. Reply with each image taken, the pages that use it (grep for its file name), any shot that failed and why, and for a new shot the Markdown to put where it belongs.

## Rules

- Real screenshots only. Never draw or edit an image to look like the app.
- Demo data goes in a throwaway database or a scratch copy, never the user's.
- Do not change application code to make a shot work; propose the change (a `data-test` attribute, a seeder) instead.
