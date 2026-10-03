---
name: review
description: Engineering review planner. Works out, from the files a change touches and with no model, which of this marketplace's plugins the change needs (four-pass-review, migration-safety, change-impact) and which follow-ups to offer (test-gap-writer), and shows that plan with the files that selected each plugin and the reason each other plugin is skipped. Use when the user asks which reviews a change needs, what engineering-review would run, or for a review plan. Runs nothing; running the selected plugins is not built yet.
argument-hint: "[target] --plan"
allowed-tools: Read, Bash(git:*), Bash(gh pr view:*), Bash(python3:*)
---

# Engineering review: plan

Decide which plugins a change needs, and show the plan. A script makes the decision from the changed paths and `registry.json`, so the same change always gets the same plan and making it costs nothing.

**This version only plans.** Running the selected plugins and merging their results is the next step and is not built yet. With or without `--plan`, show the plan and stop; without it, say in one line that running is not available yet.

You are the **lead**. You do not review or analyse anything yourself, and you launch no agents.

## Arguments

Arguments received: `$ARGUMENTS`

| Form | Meaning |
|---|---|
| *(empty)* | Working tree against `HEAD`, including untracked files. If that has no changes, the current branch against its merge-base with the default branch. |
| `123`, `#123`, or a PR URL | That pull request, via `gh`. |
| `feature/x`, `abc123`, `main...HEAD` | A ref or ref range; a single ref means `<default-branch>...<ref>`. |
| `--plan` | Show the plan. In this version, also the default. |

## Repository state

There is no launch-time preamble on purpose: a shell command run at launch, the exclamation-mark-and-backtick form, stops the whole skill from loading if it fails. The lead reads the state itself, in Step 1.

## Procedure

### Step 1 — Resolve the target

```bash
git rev-parse --show-toplevel           # fails outside a repository: say so and stop
git branch --show-current
git symbolic-ref --short refs/remotes/origin/HEAD   # the default branch as origin/<name>; if it fails, assume main
git status --short
```

- Working tree: base `HEAD`, head = working tree. If `git rev-parse --verify --quiet HEAD` prints nothing, the repository has no commits yet; use the empty tree (`git hash-object -t tree /dev/null`) as the base.
- Branch or ref: base = `git merge-base <default-branch> <ref>`, head = `<ref>`.
- PR: `gh pr view <n> --json number,title,state,baseRefName,headRefName,headRefOid`. Fetch the head if needed (`git fetch origin <headRefName>`), then base = `git merge-base origin/<baseRefName> <headRefOid>`, head = `<headRefOid>`.

### Step 2 — Plan

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/plan.py" --base <base>                # working tree
python3 "${CLAUDE_SKILL_DIR}/scripts/plan.py" --base <base> --head <head>  # a ref or PR
```

It prints JSON: the changed files, the `selected` plugins with the files that selected each (`evidence`, and `matched` for the full count), the `skipped` plugins with a `reason`, and the `follow_ups` to offer. If it exits 1, show its error and stop.

Take the plan as the script gives it. Do not add a plugin it skipped or drop one it selected; if the plan looks wrong, say so after showing it, and name the registry pattern you think is wrong.

### Step 3 — Availability

For each selected plugin and follow-up, check whether its skill (the `skill` field, e.g. `migration-safety:check`) is in your available skills. A selected plugin that is not installed is still shown, marked **not installed**, with the install command `/plugin install <name>@jarrydh-agents`. When running is built, a plugin that is not installed will be reported as not run, never as clean.

### Step 4 — Show the plan

Render it using `${CLAUDE_SKILL_DIR}/references/plan-template.md` exactly. That is your whole reply. Write no files.

## Rules

- **Plan only.** Launch no agents, run no plugin, write no files, post nothing.
- **The script decides.** Selection is the registry's patterns applied to the changed paths. Your judgement goes in a note after the plan, never into it.
- **Read-only.** Never edit files or check out a different ref in the user's working tree.
