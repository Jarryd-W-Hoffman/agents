---
name: hunt
description: Regression hunt. Reads a change's history with a script, with no model — the commits that last touched the changed lines, the fixes and reverts among them, files that always change together with the changed ones — and, only when that history has something to say, runs one read-only regression-reviewer agent to check whether the change undoes it: removes a fix's guard, re-introduces reverted code, loosens a regression test, or leaves a usual partner file behind. Writes one report and a findings.json in the shared finding contract. Use when the user asks whether a change could regress something, re-introduce an old bug, or undo an earlier fix. Read-only.
argument-hint: "[target] [--threshold 80]"
allowed-tools: Agent, Read, Grep, Glob, Write, Bash(git:*), Bash(gh pr view:*), Bash(gh issue view:*), Bash(mktemp:*), Bash(python3:*)
---

# Regression hunt

Read the history the change could regress, and only if there is some, have one `regression-reviewer` agent judge the change against it. The agent type is namespaced `regressions:regression-reviewer` when this skill is installed as a plugin; use whichever form appears in your available agent list.

You are the **lead**. You do not review anything yourself. You resolve the target, run the history scan, brief the reviewer, and write the report.

A change with no fix, revert or usual-partner history behind it costs nothing: Step 2 stops before any agent is launched.

## Arguments

Arguments received: `$ARGUMENTS`

| Form | Meaning |
|---|---|
| *(empty)* | Working tree against `HEAD`. If that has no changes, the current branch against its merge-base with the default branch. |
| `123`, `#123`, or a PR URL | That pull request, via `gh`. |
| `feature/x`, `abc123`, `main...HEAD` | A ref or ref range; a single ref means `<default-branch>...<ref>`. |
| `--threshold N` | Minimum confidence to report (default 80). |

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

If `git rev-parse --verify --quiet HEAD` prints nothing, the repository has no commits, so there is no history to regress: say so and stop.

- Working tree: base `HEAD`, head = working tree.
- Branch or ref: base = `git merge-base <default-branch> <ref>`, head = `<ref>`.
- PR: `gh pr view <n> --json number,title,body,url,state,baseRefName,headRefName,headRefOid`. Fetch the head if needed (`git fetch origin <headRefName>`), then base = `git merge-base origin/<baseRefName> <headRefOid>`, head = `<headRefOid>`. Keep the title and body as the change intent.

The base is the history that counts: everything the change could undo was committed before it.

### Step 2 — Scan the history

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/history-scan.py" --base <base>                # working tree
python3 "${CLAUDE_SKILL_DIR}/scripts/history-scan.py" --base <base> --head <head>  # a ref or PR
```

It prints JSON: `analyse` and `reason`, the `signals` counts, and per changed file the relevant commits (fixes and reverts, commits on the changed lines, with issue references and reverted SHAs) and any missing usual partners.

**If `analyse` is false, stop.** Say in one line what the history showed (the `reason`) and that nothing was reviewed. Do not launch the reviewer and do not write a report or findings file. If the script exits 1, show its error and stop.

### Step 3 — Brief and launch the reviewer

Read `${CLAUDE_SKILL_DIR}/references/reviewer-brief.md` and fill it in from Step 1 and the scan output, verbatim. List the external context sources the session has (an authenticated `gh`, issue-tracker MCP servers) so the reviewer can read the issues the commits cite.

Launch **one** `Agent` call: `subagent_type` the regression-reviewer agent type, the filled-in brief as the prompt, `name` `regressions`. Then wait. Do not review anything yourself while it runs.

If the reviewer returns nothing usable, the verdict is `INCOMPLETE`; never read its silence as a pass.

### Step 4 — Report

1. **Filter** the reviewer's findings to confidence at or above the threshold.
2. **Verdict**, computed: `FAIL` if any critical; `REQUEST_CHANGES` if any major; `PASS_WITH_NOTES` if only minor; `PASS` if none; `INCOMPLETE` if the reviewer did not report.
3. Render the report using `${CLAUDE_SKILL_DIR}/references/report-template.md` exactly. **Your reply is that report**, shown in full.

Then save, in a temporary directory outside the repository (your scratchpad directory if one is listed in your system prompt, otherwise `mktemp -d`), never in the working tree:

1. `findings.json`: the findings in the **finding contract**, `${CLAUDE_SKILL_DIR}/scripts/finding.schema.json`. One object per reported finding: `id` (`REG-1`, …), `title`, `severity`, `confidence`, `pass` (always `regressions`), `path`, `line` (in the head), `body` (the earlier commit, the invariant, and the failure scenario), and optionally `end_line`, `side`, `fix`. No other fields. With no findings, write `[]`.
2. `report.md`: the report as you showed it. If it cannot be saved, say so; `findings.json` is the result.

Validate before mentioning it:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/finding_contract.py" <dir>/findings.json
```

If it reports errors, fix the file and validate again. End your reply with one line giving the paths.

## Rules

- **Read-only.** Never edit files in the repository, never run the application, its tests or a database client, and never check out a different ref. `Write` is in this skill's `allowed-tools` for `findings.json` and `report.md` in the temporary directory and nothing else.
- **The reviewer is read-only by enforcement, not just instruction.** The plugin's PreToolUse guard (`hooks/readonly-guard.py`) denies edits, state-changing shell commands and write-style MCP tools for the `regression-reviewer` agent. If it reports a denial, treat the gap as a Note.
- **No history, no agent.** Step 2's early stop is the plugin's cost model.
- **Every finding names an earlier commit.** A finding the reviewer cannot tie to a specific fix, revert or co-change belongs to another review; keep it as one line under Notes at most.
- **Do not review yourself**, do not paste large diffs into the brief, and do not post anywhere.
