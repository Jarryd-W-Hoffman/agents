---
name: check
description: Migration safety check. Finds the database migrations in a change without a model and, only when there are some, runs one read-only migration-reviewer agent against them for what breaks in production — old code running against the new schema during the deploy, table locks and rewrites, data loss, constraints existing rows violate, edited history, and missing rollbacks — then writes one report and a findings.json in the shared finding contract. Use when the user asks whether a migration is safe to deploy, for a migration review, or to check a PR or branch that touches migrations. Read-only; never runs a migration or connects to a database.
argument-hint: "[target] [--threshold 80]"
allowed-tools: Agent, Read, Grep, Glob, Write, Bash(git:*), Bash(gh pr view:*), Bash(gh pr diff:*), Bash(gh issue view:*), Bash(mktemp:*), Bash(python3:*)
---

# Migration safety check

Find the migrations in a change, and only if there are any, have one `migration-reviewer` agent judge what happens when they run against a production database that holds data and serves traffic while the previous release is still live. The agent type is namespaced `migration-safety:migration-reviewer` when this skill is installed as a plugin; use whichever form appears in your available agent list.

You are the **lead**. You do not review migrations yourself. You resolve the target, find the migrations with a script, brief the reviewer, wait for it, and write the report.

The check costs nothing when the change has no migrations: Step 2 stops before any agent is launched. Keep it that way.

## Arguments

Arguments received: `$ARGUMENTS`

| Form | Meaning |
|---|---|
| *(empty)* | Working tree against `HEAD`, including untracked files. If that has no changes, the current branch against its merge-base with the default branch. |
| `123`, `#123`, or a PR URL | That pull request, via `gh`. |
| `feature/x`, `abc123`, `main...HEAD` | A ref or ref range; a single ref means `<default-branch>...<ref>`. |
| `--threshold N` | Minimum confidence to report (default 80). |

## Repository state

There is no launch-time preamble on purpose. A shell command run at launch, the exclamation-mark-and-backtick form, stops the whole skill from loading if it fails, and then the model carries on without these instructions: `git rev-parse HEAD` fails in a repository with no commits, and every git command fails outside a repository. So the lead reads the state itself, in Step 1, where a failure is visible and handled.

## Procedure

### Step 1 — Resolve the target

First read the repository state:

```bash
git rev-parse --show-toplevel           # fails outside a repository: say so and stop
git branch --show-current               # the current branch; empty on a detached HEAD
git symbolic-ref --short refs/remotes/origin/HEAD   # the default branch as origin/<name>; if it fails, assume main
git status --short                      # the working tree
```

If `git rev-parse --verify --quiet HEAD` prints nothing, the repository has no commits yet: every file is new, so take the base as the empty tree (`git hash-object -t tree /dev/null`) and the head as the working tree.

Determine the **base**, which is what production runs now, and the **head**:

- Working tree: base `HEAD`, head = working tree.
- Branch or ref: base = `git merge-base <default-branch> <ref>`, head = `<ref>`.
- PR: `gh pr view <n> --json number,title,body,url,state,baseRefName,headRefName,headRefOid`. Fetch the head if needed (`git fetch origin <headRefName>`), then base = `git merge-base origin/<baseRefName> <headRefOid>`, head = `<headRefOid>`. Keep the title and body, and any linked issue (`gh issue view <n> --json title,body`), as the change intent. Stop if the PR is closed or merged.

Stop and tell the user if the target cannot be resolved.

### Step 2 — Find the migrations

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/find-migrations.py" --base <base>                # working tree
python3 "${CLAUDE_SKILL_DIR}/scripts/find-migrations.py" --base <base> --head <head>  # a ref or PR
```

It prints JSON: the migrations with their status and framework, whether an added one sorts before a migration already at base (`out_of_order`), and the schema dumps, deploy and database config, and rule files at base.

**If `migrations` is empty, stop.** Say in one line that the change touches no migrations and nothing was reviewed. Do not launch the reviewer, and do not write a report or findings file. If the script exits 1, show its error and stop.

### Step 3 — Brief and launch the reviewer

Read `${CLAUDE_SKILL_DIR}/references/reviewer-brief.md` and fill it in from Step 1 and the script's output, verbatim. Note which external context sources the session has (an authenticated `gh`, MCP servers for GitHub, Jira, Linear and the like) and list them so the reviewer uses them, read-only, instead of guessing.

Launch **one** `Agent` call: `subagent_type` the migration-reviewer agent type, the filled-in brief as the prompt, `name` `migration-safety`. Then wait. Do not review anything yourself while it runs.

If the reviewer returns nothing usable, the review did not happen. The verdict is `INCOMPLETE`, and you say so; never read its silence as a pass.

### Step 4 — Report

1. **Filter** the reviewer's findings to confidence at or above the threshold.
2. **Verdict**, computed: `FAIL` if any critical; `REQUEST_CHANGES` if any major; `PASS_WITH_NOTES` if only minor; `PASS` if none; `INCOMPLETE` if the reviewer did not report.
3. Write the report using `${CLAUDE_SKILL_DIR}/references/report-template.md` exactly. Keep every finding's `MIG-` ID so the user can ask about it by name. Carry the reviewer's deploy model line: a PASS against an assumed deploy model says less than one against a written one.

Then save the result as two files, in a temporary directory outside the repository (your scratchpad directory if one is listed in your system prompt, otherwise `mktemp -d`), never in the working tree:

1. `report.md`: the report exactly as you showed it.
2. `findings.json`: the same findings in the **finding contract**, defined by `${CLAUDE_SKILL_DIR}/scripts/finding.schema.json`. One object per reported finding: `id` (`MIG-1`, …), `title`, `severity`, `confidence`, `pass` (always `migration-safety`), `path` (repo-relative), `line` (in the head version; for a deleted migration, the base-version line with `side` `LEFT`), `body` (the failure scenario and why it matters), and optionally `end_line`, `fix`, `suggestion`. Use a finding's first location if it has several; mention the others in `body`. No other fields. With no findings, write `[]`.

Validate it before saying anything about it:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/finding_contract.py" <dir>/findings.json
```

If it reports errors, fix the file and validate again. End your reply with one line giving both paths.

## Rules

- **Read-only.** Never edit files in the repository, never run a migration, seeder, `artisan`, framework CLI or database client, not even with `--pretend`, and never check out a different ref in the user's working tree. `Write` is in this skill's `allowed-tools` for `report.md` and `findings.json` in the temporary directory and nothing else.
- **The reviewer is read-only by enforcement, not just instruction.** The plugin's PreToolUse guard (`hooks/readonly-guard.py`) denies edits, state-changing shell commands, database clients and write-style MCP tools for the `migration-reviewer` agent. If the reviewer reports a denial, treat the gap as a Note, not a reason to do it yourself.
- **Do not review yourself.** If the reviewer missed something, say so under Notes; do not add findings of your own.
- **No migrations, no agent.** Step 2's early stop is the plugin's cost model. Do not launch the reviewer "just in case" on a change the script found no migrations in. If the user names a migration the script did not find, say that its layout is not one `find-migrations.py` recognises, which is a gap in the script to fix, and stop; do not guess at what else it missed.
- **Do not paste large diffs into the brief.** Give commands.
- **Do not soften or inflate.** Report the computed verdict. Do not post anywhere.
