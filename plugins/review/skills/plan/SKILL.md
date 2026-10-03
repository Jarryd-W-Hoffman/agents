---
name: plan
description: Review plan for a change. Works out from the files a change touches, with no model, which of this marketplace's plugins it needs (fourpass, migrations, regressions, impact) and which follow-ups to offer (testgaps), and shows the plan with the files that selected each plugin and the reason each other plugin is skipped. Runs nothing and costs nothing. Use when the user asks which reviews a change needs or what /review:all would run.
argument-hint: "[target]"
allowed-tools: Read, Bash(git:*), Bash(gh pr view:*), Bash(python3:*)
---

# Review plan

Decide which plugins a change needs, and show the plan. A script makes the decision from the changed paths and the plugin's `registry.json`, so the same change always gets the same plan and making it costs nothing. `/review:all` makes the same plan and then runs it.

You are the **lead**. You do not review or analyse anything, you launch no agents, and you write no files.

## Arguments

Arguments received: `$ARGUMENTS`

| Form | Meaning |
|---|---|
| *(empty)* | Working tree against `HEAD`, including untracked files. If that has no changes, the current branch against its merge-base with the default branch. |
| `123`, `#123`, or a PR URL | That pull request, via `gh`. |
| `feature/x`, `abc123`, `main...HEAD` | A ref or ref range; a single ref means `<default-branch>...<ref>`. |

## Repository state

There is no launch-time preamble on purpose: a shell command run at launch, the exclamation-mark-and-backtick form, stops the whole skill from loading if it is refused or fails. Read the state in Step 1.

## Procedure

### Step 1 — Resolve the target

```bash
git rev-parse --show-toplevel                       # fails outside a repository: say so and stop
git branch --show-current
git symbolic-ref --short refs/remotes/origin/HEAD   # the default branch as origin/<name>; if it fails, assume main
git status --short
```

- Working tree: base `HEAD`, head = working tree. If `git rev-parse --verify --quiet HEAD` prints nothing, the repository has no commits yet; use the empty tree (`git hash-object -t tree /dev/null`) as the base.
- Branch or ref: base = `git merge-base <default-branch> <ref>`, head = `<ref>`.
- PR: `gh pr view <n> --json number,title,state,baseRefName,headRefName,headRefOid`. Fetch the head if needed (`git fetch origin <headRefName>`), then base = `git merge-base origin/<baseRefName> <headRefOid>`, head = `<headRefOid>`.

### Step 2 — Plan

```bash
python3 "${CLAUDE_SKILL_DIR}/../../scripts/plan.py" --base <base>                # working tree
python3 "${CLAUDE_SKILL_DIR}/../../scripts/plan.py" --base <base> --head <head>  # a ref or PR
```

It prints JSON: the changed files, the `selected` plugins with the files that selected each, the `skipped` plugins with a `reason`, and the `follow_ups` to offer. If it exits 1, show its error and stop.

Take the plan as the script gives it. Do not add a plugin it skipped or drop one it selected; if the plan looks wrong, say so after showing it, naming the registry pattern you think is wrong.

### Step 3 — Availability, and show the plan

For each selected plugin and follow-up, check whether its skill (the `skill` field, e.g. `migrations:check`) is in your available skills. Render the plan with `${CLAUDE_SKILL_DIR}/../../references/plan-template.md` exactly. That is your whole reply; end it with one line: "Run it with `/review:all`" and the same target.

## Rules

- **Plan only.** Launch no agents, run no plugin, write no files, post nothing. This skill's `allowed-tools` has no `Agent` or `Write`.
- **The script decides.** Your judgement goes in a note after the plan, never into it.
- **Read-only.** Never edit files or check out a different ref in the user's working tree.
