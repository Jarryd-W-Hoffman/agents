---
name: readme
description: Writes or rewrites a repository's README in the shape of the user's Kite README — centred hero with badges and a screenshot, a link row, Why X?, features grouped with paired screenshots, a link into the user manual, how it works with Mermaid diagrams and pseudocode, download, getting started, how it's built with an honest why-this-stack, development, contributing and licence. Surveys the repository with a script, takes real screenshots from a plan kept in docs/screenshots.json, writes the README, and checks it with a script. Use when the user asks for a README, to refresh or redo one, to "make the README like Kite's", or to add diagrams, pseudocode or screenshots to it.
argument-hint: "[--update] [--no-screenshots] [--url <running app>]"
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git:*), Bash(python3:*), Bash(node:*), Bash(npm:*), Bash(npx:*), Bash(curl:*), Bash(ls:*), Bash(mkdir:*)
---

# README

Write the repository's README in the shape of Kite's: the template is `${CLAUDE_PLUGIN_ROOT}/references/readme-template.md`, the voice and the rules for diagrams, pseudocode and screenshots are in `${CLAUDE_PLUGIN_ROOT}/references/style.md`. Read both before writing anything.

## Arguments

Arguments received: `$ARGUMENTS`

| Form | Meaning |
|---|---|
| *(empty)* | Write the README from the template. If one exists, keep every true fact in it and restructure around the template. |
| `--update` | Keep the existing structure; bring it up to date with the code (new features, commands, screenshots, diagrams) and fill the template's gaps. |
| `--no-screenshots` | Do not run the app. Reuse the images already there and list the shots that are missing. |
| `--url <url>` | The app is already running there; use it instead of starting one. |

## Procedure

### Step 1 — Survey

```bash
git rev-parse --show-toplevel        # fails outside a repository: say so and stop
git status --short                   # note uncommitted work; never discard it
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/survey.py" --root <toplevel>
```

The survey gives the name, the GitHub slug, the stacks and their commands, the CI workflows with ready-made badges, the licence, the docs and images that exist, and what there is to screenshot. It is a guess from file names: verify what you use.

Then read, in this order: the existing README and `docs/` (keep every true fact), `CHANGELOG.md` (what shipped), the manifests and CI workflows (exact versions and commands), the routes, commands or entry points (the feature list), and enough of the code behind each feature to describe it correctly. For a big repository, read the entry points and skim; do not read every file.

### Step 2 — Plan

Decide, from what you read:

- the **emoji and one-liner** for the hero, and the **Why X?** claims, each with its proof in the code;
- the **feature groups** and what goes in each, and which screenshot follows which group;
- the **diagrams**: at least one Mermaid diagram of the real architecture or main flow, plus one per mechanism a reader needs to understand (a pipeline, a sync, a lifecycle);
- the **pseudocode**: one ```` ```text ```` block for each algorithm or rule a user would want to predict;
- the **screenshots**: the hero, one or two per feature group, a dark variant if the app has a dark theme, terminal shots for a CLI;
- which template sections do not apply, and the project's own names for the ones that do.

Say the plan to the user in a few lines (sections, diagrams, shots) and carry on; do not wait for approval unless something the README must say is unknowable from the repository, such as why a stack was chosen. Ask for that one thing.

### Step 3 — Screenshots

Skip with `--no-screenshots`. Otherwise follow `${CLAUDE_PLUGIN_ROOT}/references/screenshots.md`:

1. Add the README's shots to `docs/screenshots.json` (create it if missing; keep the manual's shots if they are there). README images go to `.github/screenshots/`.
2. Start the app with demo data, unless `--url` was given, on a spare port, in the background.
3. `node "${CLAUDE_PLUGIN_ROOT}/scripts/shoot.mjs" docs/screenshots.json --check`, then run it for real.
4. Open every image with Read. Retake any that is wrong. Stop the app.

If the app cannot be started (missing services, secrets), say what blocked it, keep the shots in the plan, and carry on without them; the check in Step 5 lists them as missing.

### Step 4 — Write

Write `README.md` from the template, in the house style. Every command, version, shortcut, path and limit comes from the repository or a command you ran. Link to `docs/manual/README.md` and list its chapters if a manual exists; if it does not, leave the **User manual** section and the features callout out and suggest `/docs:manual` at the end.

### Step 5 — Check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/docs_check.py" --root <toplevel> --readme README.md --plan docs/screenshots.json
```

Fix every error. Fix warnings that point at a real gap; a warning about a section the project should not have is fine. Run it again until it reports no errors.

### Step 6 — Report

Reply with: what the README now covers (sections, number of diagrams, pseudocode blocks and screenshots), anything you could not confirm and left out, any screenshot that could not be taken and why, and the files changed. Do not commit unless the user asks; when they do, follow the repository's commit conventions (sign-off if it checks DCO).

## Rules

- **Nothing invented.** A feature, flag, number or reason that is not in the repository or the user's words does not go in the README.
- **Real screenshots only.** Never draw a mock-up and call it a screenshot. A missing shot stays missing and is reported.
- **Do not touch the user's data.** Demo data goes in a throwaway database or a scratch copy. Never run migrations or seeders against a database the user works in.
- **Leave the code alone.** This skill edits `README.md`, `docs/screenshots.json` and the images. If the docs need a code change (a `data-test` attribute, a demo seeder), propose it; make it only if the user agrees.
