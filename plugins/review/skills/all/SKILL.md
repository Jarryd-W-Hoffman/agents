---
name: all
description: Full review of a change. Works out from the files it touches, with no model, which of this marketplace's plugins it needs (fourpass, migrations, regressions, impact), runs the selected ones in parallel, each exactly as it runs on its own, and merges their results into one report with one verdict. Offers testgaps afterwards, never without asking. Use when the user asks for a full, complete or engineering review of a change, PR or branch. To see only which plugins would run, use /review:plan.
argument-hint: "[target]"
allowed-tools: Agent, Read, Write, Bash(git:*), Bash(gh pr view:*), Bash(mktemp:*), Bash(python3:*)
---

# Review all

Decide which plugins a change needs, run them in parallel, and merge what they report into one result. A script makes the decision from the changed paths and `registry.json`; each selected plugin then runs in its own subagent, exactly as it would on its own; a second script merges their output by rules.

You are the **lead**. You do not review, analyse or write tests yourself. You plan, launch, collect, merge and report.

To see the plan without running anything, the user wants `/review:plan`, not this skill.

## Arguments

Arguments received: `$ARGUMENTS`

| Form | Meaning |
|---|---|
| *(empty)* | Working tree against `HEAD`, including untracked files. If that has no changes, the current branch against its merge-base with the default branch. |
| `123`, `#123`, or a PR URL | That pull request, via `gh`. |
| `feature/x`, `abc123`, `main...HEAD` | A ref or ref range; a single ref means `<default-branch>...<ref>`. |

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

Keep the user's own target argument (empty, the PR number, or the ref) as written: it is what each plugin is given in Step 4.

### Step 2 — Plan

Make a temporary directory outside the repository (your scratchpad directory if one is listed in your system prompt, otherwise `mktemp -d`) and save the plan in it:

```bash
python3 "${CLAUDE_SKILL_DIR}/../../scripts/plan.py" --base <base> [--head <head>]
```

Write its output to `<dir>/plan.json`. If it exits 1, show its error and stop.

Take the plan as the script gives it. Do not add a plugin it skipped or drop one it selected; if the plan looks wrong, say so in a note, naming the registry pattern you think is wrong.

### Step 3 — Availability, and show the plan

For each selected plugin and follow-up, check whether its skill (the `skill` field, e.g. `migrations:check`) is in your available skills. Render the plan with `${CLAUDE_SKILL_DIR}/../../references/plan-template.md`.

- **If nothing is selected, stop** after the plan: there is nothing to run.
- Otherwise show the plan and continue. A selected plugin that is not installed is not run; it is recorded in Step 5 as `not_installed`, which makes the verdict `INCOMPLETE`.

### Step 4 — Run the selected plugins in parallel

Read `${CLAUDE_SKILL_DIR}/../../references/runner-brief.md` and fill it in once per selected, installed plugin. Issue all the `Agent` calls **in a single message**, so they run at the same time: `subagent_type` `general-purpose`, the filled-in brief as the prompt, `name` the plugin's name. Never launch them one at a time; the total time should be the slowest plugin's, not the sum.

Each subagent runs one plugin's skill and nothing else. The plugin's own lead then launches its own agents (fourpass's four reviewers, the migrations plugin's reviewer, impact's analyst), so each plugin behaves exactly as it does when run alone.

Then wait. Do not review anything yourself while they run.

### Step 5 — Collect and merge

Each subagent replies with the block the brief asks for. Turn the replies into `<dir>/results.json`, one entry per selected plugin, copying each field as given:

```json
{
  "target": "<target description>",
  "plan": <the contents of plan.json>,
  "results": {
    "<plugin>": {"status": "reported", "findings": "<FINDINGS path>", "report": "<REPORT path>", "note": "<NOTE, if any>"},
    "<map plugin>": {"status": "reported", "impact": "<IMPACT path>", "report": "<REPORT path>"},
    "<plugin>": {"status": "nothing_to_do", "reason": "<REASON>"},
    "<plugin>": {"status": "not_installed"},
    "<plugin>": {"status": "failed", "reason": "<REASON, or: the subagent returned no usable reply>"}
  }
}
```

A subagent that returned nothing usable, or no block, is `failed`. Never record a plugin as `reported` or `nothing_to_do` unless its subagent said so. A `NOTE` goes into the entry as `"note"` and into the report's Plugins table; it never changes the status. Then:

```bash
python3 "${CLAUDE_SKILL_DIR}/../../scripts/merge.py" <dir>/results.json --out-dir <dir>
```

It validates every plugin's findings against the finding contract and the registry's prefixes, writes the merged `<dir>/findings.json` and `<dir>/summary.json`, and prints the summary with the verdict. Any selected plugin that did not report makes the verdict `INCOMPLETE`. If it exits 1, show its error and stop.

### Step 6 — Report

Render the report with `${CLAUDE_SKILL_DIR}/../../references/report-template.md` from `summary.json` and the merged `findings.json`. **Your reply is that report**, shown in full. Save the same text as `<dir>/report.md`.

Then the follow-ups. For each in `summary.json`'s `follow_ups` that is installed, offer it in one line with the command, for example `/testgaps:write <dir>/findings.json`. **Do not run a follow-up.** testgaps edits files in the repository; the user decides.

End with one line giving the paths of `report.md` and `findings.json`.

## Rules

- **The script decides selection, and the merge decides the verdict.** Your judgement goes in a note after the report, never into which plugins run or what the verdict is.
- **A plugin that did not run is never a clean result.** Not installed, failed, or no usable reply: all `INCOMPLETE`.
- **Every plugin runs as it runs alone.** Do not pass a plugin `--comment`, `--threshold` or any other flag, and do not edit its findings. Posting to a PR is not part of this skill.
- **Do not review, analyse or write tests yourself**, and do not run a follow-up without being asked.
- **Read-only, apart from the temporary directory.** Never edit files in the repository or check out a different ref in the user's working tree. `Write` is in this skill's `allowed-tools` for `plan.json`, `results.json` and `report.md` in the temporary directory and nothing else.
