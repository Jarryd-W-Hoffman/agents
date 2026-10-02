---
name: map
description: Change impact map. Finds the symbols a change touches and every reference to them with a script, then, unless --quick, runs one read-only impact-analyst agent to verify those references and find what grep cannot see — routes, scheduled tasks, queued jobs, event listeners, container bindings, tests that reach the change and changed code no test reaches, data and contracts. Writes impact.md and impact.json. Use when the user asks what a change affects, its blast radius, what depends on some code, or what to test before deploying. Read-only; does not judge whether the change is correct.
argument-hint: "[target] [--quick]"
allowed-tools: Agent, Read, Grep, Glob, Write, Bash(git:*), Bash(gh pr view:*), Bash(gh pr diff:*), Bash(gh issue view:*), Bash(mktemp:*), Bash(python3:*)
---

# Change impact map

Map what a change touches and what reaches it. A script finds the changed symbols and their references by name; one `impact-analyst` agent then verifies them and finds what a name search misses. The agent type is namespaced `change-impact:impact-analyst` when this skill is installed as a plugin; use whichever form appears in your available agent list.

You are the **lead**. You do not analyse code yourself. You resolve the target, run the scan, brief the analyst, and write the map.

The map is facts, not a review. There are no severities and no verdict, and nothing in it says the change is wrong.

## Arguments

Arguments received: `$ARGUMENTS`

| Form | Meaning |
|---|---|
| *(empty)* | Working tree against `HEAD`, including untracked files. If that has no changes, the current branch against its merge-base with the default branch. |
| `123`, `#123`, or a PR URL | That pull request, via `gh`. |
| `feature/x`, `abc123`, `main...HEAD` | A ref or ref range; a single ref means `<default-branch>...<ref>`. |
| `--quick` | The map from the script alone: direct references by name, unverified. No agent. |

## Session context (collected at launch)

Branch: !`git rev-parse --abbrev-ref HEAD`
Default branch: !`git branch --remotes --list origin/HEAD`
Working tree: !`git status --short`

The default branch line reads like `origin/HEAD -> origin/main`; the name after the arrow, without `origin/`, is the default branch. If that line is empty, assume `main`. If the branch line is empty, this is not a git repository: say so and stop.

## Procedure

### Step 1 — Resolve the target

- Working tree: base `HEAD`, head = working tree.
- Branch or ref: base = `git merge-base <default-branch> <ref>`, head = `<ref>`.
- PR: `gh pr view <n> --json number,title,body,url,state,baseRefName,headRefName,headRefOid`. Fetch the head if needed (`git fetch origin <headRefName>`), then base = `git merge-base origin/<baseRefName> <headRefOid>`, head = `<headRefOid>`. Keep the title and body as the change intent.

Stop and tell the user if the target cannot be resolved.

### Step 2 — Scan

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/impact-scan.py" --base <base>                # working tree
python3 "${CLAUDE_SKILL_DIR}/scripts/impact-scan.py" --base <base> --head <head>  # a ref or PR
```

It prints JSON: `analyse` and `reason`, the changed files with their category, and the changed symbols with their references.

**If `analyse` is false, stop.** Say in one line what changed (the `reason`, e.g. "only doc, test changed") and that there is no production impact to map. Do not launch the analyst or write any file. If the script exits 1, show its error and stop.

**With `--quick`**, skip Step 3. Get the draft map:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/impact-scan.py" --base <base> [--head <head>] --target "<target>" --impact-json
```

and go to Step 4 with it as the map. Say at the top of the report that it is unverified: names matched, collisions not removed, nothing wired by configuration found.

### Step 3 — Brief and launch the analyst

Read `${CLAUDE_SKILL_DIR}/references/analyst-brief.md` and fill it in from Step 1 and the scan output, verbatim. Note which external context sources the session has and list them.

Launch **one** `Agent` call: `subagent_type` the impact-analyst agent type, the filled-in brief as the prompt, `name` `change-impact`. Then wait. Do not analyse anything yourself while it runs.

If the analyst returns nothing usable, say the analysis did not complete, and offer the `--quick` map instead. Never present the scan as if it were verified.

### Step 4 — Write the map

1. Take the map: the analyst's JSON block, or the `--quick` draft.
2. Save it as `impact.json` in a temporary directory outside the repository (your scratchpad directory if one is listed in your system prompt, otherwise `mktemp -d`), never in the working tree, and validate it:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/impact_contract.py" <dir>/impact.json
   ```

   If it reports errors in the analyst's JSON, correct only what the errors name (a field spelled wrong, a missing `limits` line, an absolute path) and validate again. Do not add callers, entry points or risks of your own.
3. Write the report using `${CLAUDE_SKILL_DIR}/references/report-template.md` exactly, from the validated JSON, and save it beside it as `impact.md`.
4. End your reply with one line giving both paths.

## Rules

- **Read-only.** Never edit files in the repository, never run the application, its tests or a database client, and never check out a different ref in the user's working tree. `Write` is in this skill's `allowed-tools` for `impact.json` and `impact.md` in the temporary directory and nothing else.
- **The analyst is read-only by enforcement, not just instruction.** The plugin's PreToolUse guard (`hooks/readonly-guard.py`) denies edits, state-changing shell commands and write-style MCP tools for the `impact-analyst` agent. If the analyst reports a denial, treat the gap as a limit, not a reason to do it yourself.
- **Facts, not findings.** No severity, no verdict, no "this is a bug". If the analyst reports one, keep it as a single line under Limits.
- **Nothing to map, no agent.** Step 2's early stop is the plugin's cost model.
- **Do not analyse yourself** and **do not paste large diffs into the brief.** Give commands.
- Do not post anywhere.
