# four-pass-review

A Claude Code plugin that reviews a change in four independent passes, run in parallel, and merges the results into one ranked report.

| Pass | Agent | Question it answers |
|---|---|---|
| Completeness | `completeness-reviewer` | Is everything that should be in this change actually here? |
| Correctness | `correctness-reviewer` | Does the code that is here behave as intended? |
| Compliance | `compliance-reviewer` | Does the change obey the explicit, written rules (CLAUDE.md, policies, ADRs, licences, regulation)? |
| Consistency | `consistency-reviewer` | Does the change fit the implicit conventions of the surrounding codebase? |

Each agent is usable on its own. The `review` skill runs all four together.

## Why four passes

A single "review this" prompt asks one context window to hold four different mental models at once, and the result skews toward whatever the model notices first. Splitting the work by question, not by file, gives each reviewer a narrow brief, a fresh context, and an explicit list of what to leave to the other passes. The passes are designed not to overlap:

- **Completeness** compares the change against its stated intent (PR description, issue, commit messages, and what the shape of the change implies). It greps the repo to confirm new symbols are wired up and old ones are gone.
- **Correctness** traces inputs through the changed code, including failure of every external call, and must state the concrete failure scenario for every finding.
- **Compliance** first discovers the written rule sources in the repo, then only reports findings it can tie to a quoted rule and its location.
- **Consistency** reads sibling modules to establish the local convention, then only reports drift it can back with an in-repo precedent.

All four share one confidence rubric (0 to 100, default report threshold 80), one severity scale (critical, major, minor), one false-positive list, and one output format with pass-prefixed finding IDs (`CMP-`, `COR-`, `CPL-`, `CNS-`) so the lead can merge them mechanically.

## External tooling, strictly read-only

The reviewers can use whatever MCP servers and CLIs the session already has, such as GitHub or GitLab, Jira, Linear, Confluence, Notion and Sentry, to pull in PR descriptions, ticket acceptance criteria, prior review comments, ADRs and CI status. They are never allowed to change anything. Read-only is enforced at three layers:

| Layer | Mechanism | What it does |
|---|---|---|
| Tool access | `tools:` / `disallowedTools:` in each agent | Grants Read, Grep, Glob, Bash, WebFetch, WebSearch and all MCP tools (`mcp__*`); removes Edit, Write, MultiEdit, NotebookEdit. |
| Guard hook | `hooks/hooks.json` → `hooks/readonly-guard.py` (PreToolUse) | While a reviewer agent is running: denies file edits, state-changing shell commands (`git push`, `gh pr comment`, `rm`, redirection to files, scripting languages, package managers, …) and write-style MCP tools (`create_*`, `update_*`, `add_comment`, `transition*`, …). Auto-allows recognised reads (`git diff`, `gh pr view`, `jira issue view`, `mcp__*__get_*`, `list_*`, `search_*`) so reviews do not stall on permission prompts. Fails closed: anything it cannot classify is denied with a reason telling the agent what to use instead. Has no effect on other agents or the main session. |
| Instructions | "External tooling (read-only)" section in every agent prompt | Tells the reviewer what sources to use, that every call must be a read, and not to work around a denial. |

Verified end to end in a headless session: a reviewer agent ran `git status` and `git log` without prompts, and had `git push --dry-run`, `gh pr comment`, and `echo hi > file` denied before execution with the guard's reason text. Some Claude Code builds do not expose Grep and Glob to subagents with an explicit `tools:` list; the reviewers then fall back to `grep`, `rg` and `find` through Bash, which the guard auto-allows.

The guard is standard-library Python with a unit-test suite (`python3 hooks/test_readonly_guard.py`). Two environment variables tune it without editing code, as comma-separated globs matched against tool names or shell commands:

```bash
READONLY_GUARD_ALLOW="mcp__context7__*,mcp__mytracker__frobnicate"   # extra reads the guard cannot infer
READONLY_GUARD_DENY="mcp__github__*"                                # deny wins over allow
```

If you copy the agents into a project's `.claude/agents/` instead of installing the plugin, the hook is not loaded automatically. Add it to that project's `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [{ "hooks": [{ "type": "command",
      "command": "READONLY_GUARD_AGENTS='*-reviewer' python3 /path/to/agents/hooks/readonly-guard.py" }] }]
  }
}
```

## Installation

**Try it without installing** (loads for one session):

```bash
claude --plugin-dir /path/to/agents
```

**Install from this repo as a local marketplace:**

```text
/plugin marketplace add /path/to/agents
/plugin install four-pass-review@jarrydh-agents
```

**Or copy the pieces into a project** (no namespace prefix):

```bash
cp agents/*.md            your-project/.claude/agents/
cp -r skills/review       your-project/.claude/skills/
```

Restart Claude Code after installing. The agents appear in `/agents`; the skill appears as `/four-pass-review:review` (or `/review` when copied into a project).

## Usage

```text
/four-pass-review:review                       # working tree (staged + unstaged), or branch vs default branch if clean
/four-pass-review:review 142                   # pull request #142
/four-pass-review:review main...feature/x      # a ref range
/four-pass-review:review src/billing/          # specific paths, read as whole files
/four-pass-review:review --passes correctness,compliance
/four-pass-review:review 142 --threshold 70 --no-verify
/four-pass-review:review 142 --comment         # also post it to the PR: one review, inline comment per finding
/four-pass-review:review 142 --comment=summary # or as a single ordinary PR comment
```

Individual agents can be invoked in plain language, and Claude will also delegate to them on its own when their description matches the request:

```text
Use the compliance-reviewer agent on the current diff.
Run the correctness-reviewer against PR 142.
```

## How the skill works

1. **Resolve the target** into a Review Packet: base and head, diff command, changed-file stats, rule-file paths, and the change's stated intent.
2. **Launch the four reviewers in parallel.** With [agent teams](https://code.claude.com/docs/en/agent-teams) enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) the lead creates a team and gives each teammate one pass. Otherwise it spawns four subagents in a single message. Reviewers receive commands to reproduce the diff, not the diff itself, so large changes do not blow up their context.
3. **Verify borderline findings.** Findings between the threshold and 89 confidence go to a lightweight verifier that re-derives them from the code. Refuted findings are dropped.
4. **Merge.** Filter by threshold, deduplicate across passes (the owning pass keeps the finding), rank by severity then confidence, and compute the verdict: `FAIL` on any critical, `PASS_WITH_NOTES` on any other finding, else `PASS`.
5. **Report** in a fixed format, and optionally post it to the PR. With `--comment` the lead runs `skills/review/scripts/post-review.py`, which creates one pull-request review (event `COMMENT`, so it never approves or blocks a merge) with an inline comment per finding anchored at its file and line on the head commit, and the verdict and pass summaries as the review body. Findings on lines GitHub cannot anchor (outside the diff) are listed in the body instead. The script dry-runs first, and it is the only write the skill ever performs.

The skill is read-only. It never edits files, runs builds or tests, or checks out other refs. Fixing findings is a separate step you ask for afterwards.

## Output

Each reviewer returns:

```markdown
## Correctness review

**Target:** main...feature/x, 9 files
**Verdict:** FAIL
**Summary:** One unguarded null dereference on the new export path.

### Findings

#### [COR-1] Export crashes when invoice has no customer
- **Severity:** critical
- **Confidence:** 92
- **Location:** `app/Services/InvoiceExporter.php:48`
- **Evidence:** `$invoice->customer->email` is read without a null check; `customer_id` is nullable in the migration.
- **Failure scenario:** Exporting an invoice created via the API without a customer throws and aborts the whole batch.
- **Why it matters:** Nightly export job fails for the entire tenant.
- **Suggested fix:** Guard with `$invoice->customer?->email` and skip or log the row.
```

The merged report groups findings by severity with the verdict at the top. See `skills/review/references/report-template.md`.

## Configuration

| Knob | Where | Default |
|---|---|---|
| Confidence threshold | `--threshold N` | 80 |
| Passes to run | `--passes a,b,c` | all four |
| Verification of borderline findings | `--no-verify` to skip | on |
| Model for reviewers | `model:` in each `agents/*.md` | `inherit` (the session's model) |
| Agent teams vs subagents | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` in settings | auto-detected |

Agents are deliberately read-only (`disallowedTools` plus the guard hook). Keep both when customising them.

## Layout

```text
.claude-plugin/
  plugin.json            plugin manifest
  marketplace.json       lets this repo be added as a local marketplace
agents/
  completeness-reviewer.md
  correctness-reviewer.md
  compliance-reviewer.md
  consistency-reviewer.md
skills/review/
  SKILL.md               the orchestrating skill
  references/
    reviewer-prompt.md   the brief sent to each reviewer
    report-template.md   the merged report format
  scripts/
    post-review.py       posts the report to a PR as inline review comments
    test_post_review.py  unit tests for the poster
hooks/
  hooks.json             registers the PreToolUse read-only guard
  readonly-guard.py      the guard (stdlib Python)
  test_readonly_guard.py unit tests for the guard
.github/workflows/validate.yml
```

## Development

Validate manifests, agents and skills (also runs in CI):

```bash
claude plugin validate --strict .                          # marketplace manifest
claude plugin validate --strict .claude-plugin/plugin.json # plugin manifest
claude plugin validate --strict agents
claude plugin validate --strict skills
```

Run the tests:

```bash
python3 hooks/test_readonly_guard.py
python3 skills/review/scripts/test_post_review.py
```

Check the token cost of what the plugin loads into a session:

```bash
claude plugin details four-pass-review
```

When editing an agent, keep the shared sections (out-of-scope list, false-positive list, confidence rubric, output format) identical across all four files; the skill's merge step depends on them.

## License

MIT. See [LICENSE](LICENSE).
