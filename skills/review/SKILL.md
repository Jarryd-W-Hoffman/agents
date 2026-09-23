---
name: review
description: Four-pass code review. Runs four independent reviewer agents in parallel (completeness, correctness, compliance, consistency) against the same change, verifies borderline findings, and merges everything into one ranked report. Use when the user asks for a code review, PR review, pre-merge check, or "four-pass review" of the working tree, a branch, a PR number, or specific paths. Read-only; it never edits files or posts anywhere unless asked with --comment.
argument-hint: "[target] [--passes completeness,correctness,compliance,consistency] [--threshold 80] [--no-verify] [--comment]"
allowed-tools: Agent, Read, Grep, Glob, Bash(git *), Bash(gh pr view *), Bash(gh pr diff *), Bash(gh issue view *)
---

# Four-pass code review

Run four independent reviewer agents in parallel, one per pass, then merge their findings into a single ranked report. Each pass answers a different question and is told to leave the other three questions alone, so the passes do not duplicate each other:

| Pass | Agent | Question |
|---|---|---|
| Completeness | `completeness-reviewer` | Is everything that should be in this change actually here? |
| Correctness | `correctness-reviewer` | Does the code that is here behave as intended? |
| Compliance | `compliance-reviewer` | Does the change obey the explicit, written rules (CLAUDE.md, policies, ADRs, licences, regulation)? |
| Consistency | `consistency-reviewer` | Does the change fit the implicit conventions of the surrounding codebase? |

When this skill is installed as a plugin the agent types are namespaced: `four-pass-review:completeness-reviewer`, and so on. Use whichever form appears in your available agent list.

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
| `--comment` | After the report, post it as a single PR comment. Requires a PR target. |

## Session context (collected at launch)

Branch: !`git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "not a git repo"`
Default branch: !`git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#origin/##' | grep . || echo "unknown (assume main)"`
Working tree: !`git status --short 2>/dev/null | head -40`
Diff stat vs HEAD: !`git diff HEAD --stat 2>/dev/null | tail -15`

## Procedure

### Step 1 — Resolve the target into a Review Packet

Build a **Review Packet** the reviewers can act on without guessing. Prefer commands over pasted content: give reviewers the exact `git`/`gh` commands that reproduce the diff, not the diff itself, unless it is under ~150 lines.

1. Determine base and head:
   - Working tree: base `HEAD`, head = working tree. Reviewers run `git diff HEAD`.
   - Branch/ref: base = `git merge-base <default-branch> <ref>`, head = `<ref>`. Reviewers run `git diff <base>...<head>` and read files at head with `git show <head>:<path>` when the checkout differs.
   - PR: `gh pr view <n> --json number,title,body,url,baseRefName,headRefName,headRefOid,files`. Fetch the head if needed (`git fetch origin <headRefName>`), then treat as branch/ref with base `origin/<baseRefName>`. Keep the PR title/body and any linked issues (`gh issue view <n> --json title,body`) for the completeness pass.
   - Paths: base `HEAD`, scope limited to the paths. Tell reviewers to read the full files, not only the diff.
2. Collect: changed file list with `--stat`, total changed lines, and the list of relevant rule files: root `CLAUDE.md`, any `CLAUDE.md`, `AGENTS.md`, `.claude/rules/*.md` in or above the changed directories (`git ls-files '*CLAUDE.md' 'AGENTS.md' '.claude/rules/*.md'`), plus `CONTRIBUTING.md` and `SECURITY.md` if present. List paths only; the reviewers read them.
3. Note which external context sources are available in this session and relevant to the target: an authenticated `gh` or `glab` CLI, and any MCP servers for GitHub, GitLab, Jira, Linear, Confluence, Notion, Sentry or similar. List them in the packet so reviewers use them (read-only) instead of guessing about tickets or prior review discussion. You may use the same sources yourself to fill in the change's intent.
4. Record the effective `--threshold` and `--passes`.

Stop here and tell the user if there is nothing to review (empty diff, PR closed or already merged, unknown ref).

If the diff exceeds roughly 3,000 changed lines, say so, suggest splitting the change, and continue anyway.

### Step 2 — Brief and launch the reviewers in parallel

Read `${CLAUDE_SKILL_DIR}/references/reviewer-prompt.md` and fill in the template once per selected pass. All four briefs are identical except for the pass name and agent type.

Launch in one of two modes:

**Mode A — agent team (preferred when available).** If `TeamCreate` is in your tool list (agent teams enabled), create a team, spawn one teammate per pass using the matching reviewer agent type, give each its brief, and wait for all of them to report back. Do not assign a teammate more than one pass. Do not review while waiting.

**Mode B — parallel subagents (fallback).** Otherwise, issue all `Agent` calls **in a single message** so they run concurrently, one per pass, with `subagent_type` set to the reviewer agent type and the brief as the prompt. Never launch them one at a time.

In both modes, name each spawn after its pass (`completeness`, `correctness`, …) so the reports are attributable.

### Step 3 — Verify borderline findings (skip with `--no-verify`)

After all reports are in, collect findings whose confidence is between the threshold and 89, plus any finding that two passes reported differently. Cap at 6, preferring higher severity. For each, in one parallel batch, spawn a lightweight verifier (`general-purpose`, `model: haiku` or `sonnet`) with: the Review Packet, the single finding verbatim, and this instruction:

> Independently verify whether this finding is real by reading the code. Do not trust the finding's reasoning; re-derive it. Reply with `CONFIRMED`, `REFUTED`, or `UNCERTAIN`, one sentence of evidence, and a revised confidence 0–100.

Drop `REFUTED` findings. Replace confidence with the verifier's number for `CONFIRMED` and `UNCERTAIN`. Findings at 90+ are kept without verification.

### Step 4 — Merge

1. **Filter** to confidence ≥ threshold.
2. **Deduplicate.** Two findings are duplicates when they point at the same file and overlapping lines and describe the same underlying problem. Keep the one from the pass that owns the problem (bugs → correctness, written rules → compliance, missing work → completeness, pattern drift → consistency) and append "also raised by <pass>" to it.
3. **Rank** by severity (critical, major, minor), then by confidence descending, then by file path.
4. **Verdict**: `FAIL` if any critical finding remains; `PASS_WITH_NOTES` if only major or minor; `PASS` if none.

### Step 5 — Report

Write the report using `${CLAUDE_SKILL_DIR}/references/report-template.md` exactly. Keep it terse: findings first, one line of summary per pass, no praise section unless the user asks. Every finding keeps its original ID (`CMP-`, `COR-`, `CPL-`, `CNS-`) so the user can ask about it by name.

If `--comment` was given and the target is a PR, post the report with `gh pr comment <n> --body-file <tempfile>`. Do not post otherwise. Do not post if the verdict could not be computed.

## Rules

- **Read-only.** Never edit files, run builds, tests, formatters or type-checkers, and never check out a different ref in the user's working tree. If the user wants fixes, that is a separate follow-up after the report.
- **Reviewers are read-only by enforcement, not just instruction.** The plugin's PreToolUse guard (`hooks/readonly-guard.py`) denies edits, state-changing shell commands and write-style MCP tools for the four reviewer agents, and auto-allows recognised reads. If a reviewer reports that something was denied, treat the gap as a Note, not a reason to do the write yourself. The only write this skill ever performs is the optional `--comment` post, done by you, the lead.
- **Do not review yourself.** Your value is orchestration and synthesis; the passes are the reviewers.
- **Do not paste large diffs into briefs.** Give commands.
- **Do not soften or inflate.** Report the reviewers' verdicts as computed. If a pass failed to run or returned nothing usable, say so in the report under that pass rather than silently omitting it.
- If the user asks for a single pass ("just check compliance"), run only that pass and skip the merge; return its report directly.
