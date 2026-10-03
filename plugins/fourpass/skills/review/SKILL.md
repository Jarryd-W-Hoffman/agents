---
name: review
description: Four-pass code review. Runs four independent reviewer agents in parallel (completeness, correctness, compliance, consistency) against the same change, verifies borderline findings, and merges everything into one ranked report. Use when the user asks for a code review, PR review, pre-merge check, or "four-pass review" of the working tree, a branch, a PR number, or specific paths. Read-only; it never edits files or posts anywhere unless asked with --comment.
argument-hint: "[target] [--passes completeness,correctness,compliance,consistency] [--threshold 80] [--since <ref>] [--no-verify] [--comment | --comment=summary]"
allowed-tools: Agent, Read, Grep, Glob, Write, Bash(git:*), Bash(gh pr view:*), Bash(gh pr diff:*), Bash(gh pr checks:*), Bash(gh issue view:*), Bash(gh api:*), Bash(mktemp:*), Bash(python3:*)
---

# Four-pass code review

Run four independent reviewer agents in parallel, one per pass, then merge their findings into a single ranked report. Each pass answers a different question and is told to leave the other three questions alone, so the passes do not duplicate each other:

| Pass | Agent | Question |
|---|---|---|
| Completeness | `completeness-reviewer` | Is everything that should be in this change actually here? |
| Correctness | `correctness-reviewer` | Does the code that is here behave as intended? |
| Compliance | `compliance-reviewer` | Does the change obey the explicit, written rules (CLAUDE.md, policies, ADRs, licences, regulation)? |
| Consistency | `consistency-reviewer` | Does the change fit the implicit conventions of the surrounding codebase? |

When this skill is installed as a plugin the agent types are namespaced: `fourpass:completeness-reviewer`, and so on. Use whichever form appears in your available agent list.

You are the **lead**. You do not review code yourself. You resolve the target, brief the reviewers, wait for all four, verify borderline findings, and write the merged report.

## Arguments

Arguments received: `$ARGUMENTS`

| Form | Meaning |
|---|---|
| *(empty)* | Working tree: staged + unstaged changes (`git diff HEAD`). If empty, the current branch against its merge-base with the default branch. |
| `123`, `#123`, or a PR URL | That pull request, via `gh`. |
| `feature/x`, `abc123`, `main..HEAD`, `main...HEAD` | A ref or ref range; a single ref means `<default-branch>...<ref>`. |
| `src/billing/ path/to/file.ts` | Those paths, reviewed as whole files plus any diff they carry. |
| `--passes a,b` | Run only the named passes (default: all four). |
| `--threshold N` | Minimum confidence to report (default 80). |
| `--no-verify` | Skip the verification step for borderline findings. |
| `--since <ref>` | Review only what landed after `<ref>`, instead of the whole change. `--since last` asks the PR what this tool reviewed previously. |
| `--comment` | After the report, post it to the PR as one review: the summary as the review body, an inline comment per finding at its file and line, and the review event set from the verdict (`PASS` and `PASS_WITH_NOTES` approve, `REQUEST_CHANGES` and `FAIL` request changes). Requires a PR target. |
| `--comment=summary` | Post the report as a single ordinary PR comment instead of inline comments. |

## Repository state

There is no launch-time preamble on purpose. A shell command run at launch, the exclamation-mark-and-backtick form, stops the whole skill from loading if it is refused or fails, and the model then carries on without these instructions. A pipe or a `||` fallback does not match a `Bash(git:*)` permission, so in a session without blanket Bash permission such a preamble is refused outright. Read the state in Step 1 instead.

## Procedure

### Step 1 — Resolve the target into a Review Packet

First read the repository state:

```bash
git rev-parse --show-toplevel                       # fails outside a repository: say so and stop
git branch --show-current                           # the current branch; empty on a detached HEAD
git symbolic-ref --short refs/remotes/origin/HEAD   # the default branch as origin/<name>; if it fails, assume main
git status --short
git diff HEAD --stat
```

Build a **Review Packet** the reviewers can act on without guessing. Prefer commands over pasted content: give reviewers the exact `git`/`gh` commands that reproduce the diff, not the diff itself, unless it is under ~150 lines.

1. Determine the bases and head. There are **two** bases and they are not interchangeable:
   - the **review base** — what the diff is taken against, i.e. what gets reviewed;
   - the **rule base** — the revision whose written rules bind the change.

   They are the same except under `--since`, which moves the review base only. The rule base is always the revision the change branched from, never a commit belonging to the change: rules that a change introduced cannot be the rules it is judged by, and an incremental re-review must not become the way around that.

   - Working tree: base `HEAD`, head = working tree. Reviewers run `git diff HEAD`.
   - Branch/ref: base = `git merge-base <default-branch> <ref>`, head = `<ref>`. Reviewers run `git diff <review base>...<head>` and read files at head with `git show <head>:<path>` when the checkout differs.
   - PR: `gh pr view <n> --json number,title,body,url,baseRefName,headRefName,headRefOid,files`. Fetch the head if needed (`git fetch origin <headRefName>`), then treat as branch/ref with base `origin/<baseRefName>`. Keep the PR title/body and any linked issues (`gh issue view <n> --json title,body`) for the completeness pass.
   - Paths: base `HEAD`, scope limited to the paths. Tell reviewers to read the full files, not only the diff.
   With `--since <ref>`, set the **review base** to `<ref>` so the diff covers only what landed after it. Leave the **rule base** alone. `--since last` means "since the commit this tool last reviewed": get it with

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/post-review.py" --pr <n> --last-reviewed
   ```

   which prints a sha, or exits 1 with nothing when the PR has no earlier review from this plugin — in that case say so and review the whole change. `--since` is only meaningful for a PR or branch target. Say in the report header that the review was incremental and from which base, so nobody reads a clean result as a verdict on the whole change.

2. Collect: changed file list with `--stat`, total changed lines, and the list of relevant rule files: root `CLAUDE.md`, any `CLAUDE.md`, `AGENTS.md`, `.claude/rules/*.md` in or above the changed directories, plus `CONTRIBUTING.md` and `SECURITY.md` if present. List paths only; the reviewers read them.

   Enumerate them **at the rule base**, not from the working tree and not at the review base: `git ls-tree -r --name-only <rule base>`, filtered to those names. Three reasons. On a PR or ref target nothing is checked out at the head, so `git ls-files` and the files on disk describe whatever branch the session is sitting on, not the change under review. The rules that bind a change are the ones in force when it was written, so a change cannot introduce a rule that excuses it. And under `--since` the review base is a commit *belonging to the change*, which may already carry that change's own rule edits — reading rules there would hand an incremental re-review the loophole the rule base exists to close. Tell the reviewers to read each one with `git show <rule base>:<path>`.

   Then diff the rule files themselves across the **whole** change, not the incremental range: `git diff <rule base>...<head> -- <paths>` (or `git diff HEAD -- <paths>` for a working tree). Scoping this to `--since` would let a rule edit made before the last review disappear from the packet. If the change edits any of them, list them under "Rule sources changed by this change" and note that the compliance pass judges against the rule-base version and reports the edit for a human rather than adopting it.
3. Note which external context sources are available in this session and relevant to the target: an authenticated `gh` or `glab` CLI, and any MCP servers for GitHub, GitLab, Jira, Linear, Confluence, Notion, Sentry or similar. List them in the packet so reviewers use them (read-only) instead of guessing about tickets or prior review discussion. You may use the same sources yourself to fill in the change's intent.
4. Record the effective `--threshold` and `--passes`.

Stop here and tell the user if there is nothing to review (empty diff, PR closed or already merged, unknown ref).

If the diff exceeds roughly 3,000 changed lines, say so, suggest splitting the change, and continue anyway.

### Step 2 — Brief and launch the reviewers in parallel

Read `${CLAUDE_SKILL_DIR}/references/reviewer-prompt.md` and fill in the template once per selected pass. All four briefs are identical except for the pass name and agent type.

Issue all `Agent` calls **in a single message** so they run concurrently: one per selected pass, `subagent_type` set to the reviewer agent type, the filled-in brief as the prompt, and `name` set to the pass (`completeness`, `correctness`, …) so the reports are attributable. Never launch them one at a time — four sequential reviews cost four times the wall clock for no benefit.

Then wait. Do not review anything yourself while they run.

If the session has agent teams enabled, named spawns are already teammates: `ListAgents` lists them and `SendMessage` continues one with its context intact, which is how to ask a reviewer to expand on a finding rather than re-running its whole pass. Neither is required, and nothing here changes if teams are off.

If a reviewer returns nothing usable, that pass has not reported. Say so in the report and treat the verdict as `INCOMPLETE` (Step 4) rather than reading its silence as "found nothing".

### Step 3 — Verify borderline findings (skip with `--no-verify`)

After all reports are in, collect findings whose confidence is between the threshold and 89, plus any finding that two passes reported differently. Cap at 6, preferring higher severity. For each, in one parallel batch, spawn a lightweight verifier (`general-purpose`, `model: haiku` or `sonnet`) with: the Review Packet, the single finding verbatim, and this instruction:

> Independently verify whether this finding is real by reading the code. Do not trust the finding's reasoning; re-derive it. Reply with `CONFIRMED`, `REFUTED`, or `UNCERTAIN`, one sentence of evidence, and a revised confidence 0–100.

Drop `REFUTED` findings. Replace confidence with the verifier's number for `CONFIRMED` and `UNCERTAIN`. Findings at 90+ are kept without verification.

### Step 4 — Merge

1. **Filter** to confidence ≥ threshold.
2. **Deduplicate.** Two findings are duplicates when they point at the same file and overlapping lines and describe the same underlying problem. Keep the one from the pass that owns the problem (bugs → correctness, written rules → compliance, missing work → completeness, pattern drift → consistency) and append "also raised by <pass>" to it.
3. **Rank** by severity (critical, major, minor), then by confidence descending, then by file path.
4. **Check coverage first.** A pass that failed to run, errored, or returned nothing usable has *not* reported "no findings" — it has reported nothing at all, and the two must never look alike. If any selected pass is in that state, the verdict is `INCOMPLETE`, whatever the surviving findings say. Name the pass and what went wrong in the header and under Pass summaries.

   This is the difference between a review that found nothing wrong and a review that did not happen. `PASS` approves the pull request under `--comment`; a crashed compliance pass must never be able to do that.

5. **Verdict**, when every selected pass reported: `FAIL` if any critical finding remains; `REQUEST_CHANGES` if any major; `PASS_WITH_NOTES` if only minor; `PASS` if none. Four levels, so a change with several major findings is not filed under the same word as one with a single nitpick. `INCOMPLETE` sits outside the scale: it says the review is not a verdict at all, and it neither approves nor blocks.

### Step 5 — Report

Write the report using `${CLAUDE_SKILL_DIR}/references/report-template.md` exactly. Keep it terse: findings first, one line of summary per pass, no praise section unless the user asks. Every finding keeps its original ID (`CMP-`, `COR-`, `CPL-`, `CNS-`) so the user can ask about it by name.

Then save the result as two files, on every run, in a temporary directory outside the repository (your scratchpad directory if one is listed in your system prompt, otherwise `mktemp -d`), never in the working tree:

1. `report.md`: the report exactly as you showed it.
2. `findings.json`: the same findings in the **finding contract**, defined by `${CLAUDE_SKILL_DIR}/scripts/finding.schema.json`. A list with one object per reported finding, fields `id`, `title`, `severity`, `confidence`, `pass`, `path` (repo-relative), `line` (in the head version), `body` (the "why it matters" sentence plus key evidence), and optionally `end_line`, `side` (`LEFT` only for a finding about deleted code, in which case `line` is the base-version number), `fix`, `suggestion`. Use a finding's first location if it has several; mention the others in `body`. No other fields. With no findings, write `[]`.

Validate it before saying anything about it:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/finding_contract.py" <dir>/findings.json
```

If it reports errors, fix the file and validate again; the errors name the finding and the field. End your reply with one line giving both paths, and that `findings.json` is what `/testgaps:write` takes. Other tools read this file rather than parsing the report, which is free to change shape; the contract is not.

If `--comment` was given and the target is a PR, post it with the helper script, which creates one pull-request review carrying the summary as its body, an inline comment per finding, and the event the verdict implies:

1. Use the `findings.json` you just validated. The script validates it again and refuses to post one that breaks the contract.
2. Write `summary.md` in the same directory: the report's header block and the "Pass summaries" section only (no findings; they become the inline comments).
3. Dry-run first, then post:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/post-review.py" --pr <n> --findings <dir>/findings.json --summary <dir>/summary.md --dry-run
python3 "${CLAUDE_SKILL_DIR}/scripts/post-review.py" --pr <n> --findings <dir>/findings.json --summary <dir>/summary.md
```

A finding may also carry `suggestion`: the literal replacement text for its anchored lines, rendered as a GitHub ```suggestion block the author can commit in one click. Give it only when the fix really is a drop-in replacement for exactly those lines, and only on a head-side finding — it is dropped for `side: "LEFT"` and for findings outside the diff, which GitHub cannot apply a suggestion to.

Re-running is expected, so the script supersedes its own earlier review by default: it blanks that review's body and deletes its inline comments before posting the new one, which keeps the PR from collecting duplicates. `--on-existing skip` leaves the PR alone and `--on-existing add` posts anyway. In `--comment=summary` mode the earlier comment is edited in place instead. The dry run reports what it would supersede.

The script parses the PR diff and anchors each finding to its line on the head commit. GitHub can only anchor lines that appear in the diff, so findings on other lines are listed in the review body under "Findings outside the diff"; the dry run shows which. With `--comment=summary`, pass `--mode summary` to post one ordinary comment instead. Both modes refuse a PR that is not open. Tell the user the review URL the script prints.

The script reads `**Verdict:**` from `summary.md` and maps it to the review event on one question, does this block the merge: `PASS` and `PASS_WITH_NOTES` approve, since minor findings are nits, and `REQUEST_CHANGES` and `FAIL` request changes. A verdict it cannot read falls back to a plain comment. Pass `--verdict <X>` to override it. Approving and requesting changes are real, visible actions on the PR; the user asking for `--comment` is what authorises them, so do not ask again. GitHub refuses both on the user's own pull request, and the script then posts the same review as a plain comment and says so.

Do not post otherwise. Do not post if the verdict could not be computed or the PR is not open.

## Rules

- **Read-only.** Never edit files in the repository, run builds, tests, formatters or type-checkers, and never check out a different ref in the user's working tree. The temporary files (`report.md`, `findings.json`, and `summary.md` for `--comment`) live outside the working tree; `Write` is in this skill's `allowed-tools` for those files and nothing else. If the user wants fixes, that is a separate follow-up after the report.
- **Reviewers are read-only by enforcement, not just instruction.** The plugin's PreToolUse guard (`hooks/readonly-guard.py`) denies edits, state-changing shell commands and write-style MCP tools for the four reviewer agents, and auto-allows recognised reads. If a reviewer reports that something was denied, treat the gap as a Note, not a reason to do the write yourself. The only write this skill ever performs outside its temporary directory is the optional `--comment` post, done by you, the lead.
- **Do not review yourself.** Your value is orchestration and synthesis; the passes are the reviewers.
- **Do not paste large diffs into briefs.** Give commands.
- **Do not soften or inflate.** Report the reviewers' verdicts as computed. If a pass failed to run or returned nothing usable, say so in the report under that pass rather than silently omitting it.
- If the user asks for a single pass ("just check compliance"), run only that pass and skip the merge; return its report directly.
