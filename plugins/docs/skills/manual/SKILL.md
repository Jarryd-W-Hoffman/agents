---
name: manual
description: Writes a user manual in the shape of the user's Kite manual — docs/manual/README.md with a contents table, conventions and how the screenshots are taken, and one NN-topic.md chapter per feature area, each with an intro, a screenshot, a Mermaid "How it works" diagram, pseudocode, step-by-step instructions, tables, tips and see also. Plans the chapters, takes real screenshots from docs/screenshots.json, then runs one manual-writer agent per chapter in parallel, checks the result with a script and links it from the README. Use when the user asks for a user manual, user guide, docs for every feature, or to add or redo chapters.
argument-hint: "[chapter-slug ...] [--no-screenshots] [--url <running app>]"
allowed-tools: Agent, Read, Grep, Glob, Write, Edit, Bash(git:*), Bash(python3:*), Bash(node:*), Bash(npm:*), Bash(npx:*), Bash(curl:*), Bash(ls:*), Bash(mkdir:*)
---

# User manual

Write the repository's user manual in the shape of Kite's: the template is `${CLAUDE_PLUGIN_ROOT}/references/manual-template.md`, the voice and the rules for diagrams, pseudocode and screenshots are in `${CLAUDE_PLUGIN_ROOT}/references/style.md`. Read both first.

You are the **lead**. You survey, plan the chapters, write the index, take the screenshots, brief the writers, check their work and link the manual from the README. The chapters themselves are written by `manual-writer` agents, one per chapter, in parallel. The agent type is namespaced `docs:manual-writer` when this plugin is installed; use whichever form appears in your available agent list.

## Arguments

Arguments received: `$ARGUMENTS`

| Form | Meaning |
|---|---|
| *(empty)* | The whole manual. Existing chapters are rewritten to the template, keeping every true fact. |
| `links graph` | Only these chapters (by slug, with or without the number). New slugs become new chapters; the index is updated to match. |
| `--no-screenshots` | Do not run the app. Reuse the images that exist and list the shots that are missing. |
| `--url <url>` | The app is already running there; use it. |

## Procedure

### Step 1 — Survey

```bash
git rev-parse --show-toplevel        # fails outside a repository: say so and stop
git status --short
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/survey.py" --root <toplevel>
```

Read the README, any existing manual, `CHANGELOG.md`, the routes, commands or entry points, the UI's pages and menus, the settings and their defaults, and the keyboard shortcuts. You need enough to list every feature a user can reach and where its code is; the writers read the code in depth.

### Step 2 — Plan the chapters

Follow "Planning the chapters" in the manual template. For each chapter record:

- `NN-slug.md`, title, emoji, and the one-line "what's in it";
- the **source files** that implement it (routes, controllers, components, commands), so the writer starts in the right place;
- the **screenshots** it needs, by name, with what each shows;
- the chapters it should link to.

Show the plan to the user as the contents table and carry on.

### Step 3 — Screenshots

Skip with `--no-screenshots`. Otherwise follow `${CLAUDE_PLUGIN_ROOT}/references/screenshots.md`: add the manual's shots to `docs/screenshots.json` with `out` under `docs/manual/images/`, start the app with demo data unless `--url` was given, run `shoot.mjs --check` then `shoot.mjs`, open every image with Read and retake the bad ones, then stop the app. Note for each chapter which images exist and what each one shows; the writers cannot see images, so that description is how they write alt text and refer to them.

### Step 4 — Write the index

Write `docs/manual/README.md` from the template's index: intro, hero image, the contents table for every chapter in the plan, conventions, and "About the screenshots" with the real commands to bring up the demo data and retake them.

### Step 5 — Brief and launch the writers

Read `${CLAUDE_PLUGIN_ROOT}/references/writer-brief.md`. For each chapter, fill it in with: the chapter's plan entry, the source files, the screenshots that exist for it (path, alt text, what is in the picture), the full contents table (so See also links are right), the conventions, and whether to rewrite an existing chapter or write a new one.

Launch the writers **in parallel, in one message**: one `Agent` call per chapter, `subagent_type` the manual-writer agent type, the filled-in brief as the prompt, `name` the chapter's slug. With more than eight chapters, launch them in batches of eight. Do not write chapters yourself while they run.

Each writer replies with the chapter path, what it could not confirm in the code, and anything outside its chapter that should change (a missing screenshot, a wrong statement in another chapter, a README line). Collect these.

If a writer fails or returns without writing its chapter, launch it once more with the failure in the brief. If it fails again, report the chapter as not written.

### Step 6 — Check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/docs_check.py" --root <toplevel> --manual docs/manual --plan docs/screenshots.json
```

Fix every error: a broken link or missing image you fix yourself; a chapter missing its diagram or screenshot goes back to its writer with the error (SendMessage to the writer by name when available, otherwise a new writer with the error in the brief). Fix the warnings that point at a real gap. Repeat until there are no errors.

Then read the chapters side by side once for consistency: the same feature called by the same name, the same shortcut for the same action, no two chapters contradicting each other. Fix it in the chapter that is wrong.

### Step 7 — Link it from the README

Make sure `README.md` has the **User manual** section and the features callout from `${CLAUDE_PLUGIN_ROOT}/references/readme-template.md`, with every chapter in its table. Edit only those parts of the README; if it has no README worth keeping, suggest `/docs:readme`.

Run the check over both:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/docs_check.py" --root <toplevel> --readme README.md --manual docs/manual --plan docs/screenshots.json
```

### Step 8 — Report

Reply with the contents table as written, the totals (chapters, diagrams, pseudocode blocks, screenshots, from the check's counts with `--json`), the writers' unconfirmed points and suggestions, any screenshot that could not be taken and why, and the files changed. Do not commit unless the user asks.

## Rules

- **Nothing invented.** Every shortcut, setting, default, limit and behaviour is in the code. A writer that cannot confirm something leaves it out and says so; you do not add it back.
- **Real screenshots only**, taken by `shoot.mjs` from the plan. A missing shot stays missing and is reported.
- **The writers are confined by enforcement, not just instruction.** The plugin's PreToolUse guard (`hooks/docs-scope-guard.py`) lets a `manual-writer` write Markdown under `docs/` and nothing else, and denies it the shell and MCP tools. A writer that reports a denial is telling you about something for you to do.
- **Do not touch the user's data or code.** Demo data goes in a throwaway database or a scratch copy. If the docs need a code change (a `data-test` attribute, a demo seeder), propose it.
- **Do not analyse the code for the writers** and do not paste source files into the briefs. Give paths.
