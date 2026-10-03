# fourpass

A Claude Code plugin that reviews a change in four independent passes, run in parallel, and merges the results into one ranked report.

| Pass | Agent | Question it answers |
|---|---|---|
| Completeness | `completeness-reviewer` | Is everything that should be in this change actually here? |
| Correctness | `correctness-reviewer` | Does the code that is here behave as intended? |
| Compliance | `compliance-reviewer` | Does the change obey the explicit, written rules (CLAUDE.md, policies, ADRs, licences, regulation)? |
| Consistency | `consistency-reviewer` | Does the change fit the implicit conventions of the surrounding codebase? |

Each agent is usable on its own. The `review` skill runs all four together.

The reviewers are read-only, enforced by a hook and not just asked for, and they
treat everything in the change as evidence rather than instruction. See
[read-only](#external-tooling-strictly-read-only) and
[untrusted input](#the-change-is-evidence-not-instruction).

## Installation

**Try it without installing** (loads for one session):

```bash
claude --plugin-dir /path/to/agents/plugins/fourpass
```

**Install from this repo as a local marketplace:**

```text
/plugin marketplace add /path/to/agents
/plugin install fourpass@jarrydh-agents
```

**Or copy the pieces into a project** (no namespace prefix), from this plugin's directory:

```bash
cd plugins/fourpass
cp agents/*.md            your-project/.claude/agents/
cp -r skills/review       your-project/.claude/skills/
cp -r hooks               your-project/.claude/fourpass-hooks/
```

Copying the pieces does not bring the read-only guard with them — it is
registered by the plugin's `hooks.json`, which only the plugin install reads.
Wire it up by hand as shown under
[external tooling](#external-tooling-strictly-read-only), or skip it and rely
on the agents' `disallowedTools` alone.

Restart Claude Code after installing. The agents appear in `/agents`; the skill appears as `/fourpass:review` (or `/review` when copied into a project).

## Usage

```text
/fourpass:review                       # working tree (staged + unstaged), or branch vs default branch if clean
/fourpass:review 142                   # pull request #142
/fourpass:review main...feature/x      # a ref range
/fourpass:review src/billing/          # specific paths, read as whole files
/fourpass:review --passes correctness,compliance
/fourpass:review 142 --threshold 70 --no-verify
/fourpass:review 142 --comment         # also post it to the PR: inline comments, summary, and approve / request changes
/fourpass:review 142 --comment=summary # or as a single ordinary PR comment
/fourpass:review 142 --since last      # only what landed since the last review of this PR
```

Re-reviewing the same PR is the normal case, so `--comment` supersedes its own
earlier review rather than stacking a duplicate set of inline comments on it,
and records which commit it reviewed. `--since last` then reviews only what has
landed since — the report says it was incremental, so a clean result is not
mistaken for a verdict on the whole change.
A finding may carry a `suggestion`, which posts as a GitHub suggestion block
the author can commit in one click.

Individual agents can be invoked in plain language, and Claude will also delegate to them on its own when their description matches the request:

```text
Use the compliance-reviewer agent on the current diff.
Run the correctness-reviewer against PR 142.
```

## Why four passes

A single "review this" prompt asks one context window to hold four different mental models at once, and the result skews toward whatever the model notices first. Splitting the work by question, not by file, gives each reviewer a narrow brief, a fresh context, and an explicit list of what to leave to the other passes. The passes are designed not to overlap:

- **Completeness** compares the change against its stated intent (PR description, issue, commit messages, and what the shape of the change implies). It greps the repo at the head revision to confirm new symbols are wired up and old ones are gone.
- **Correctness** traces inputs through the changed code, including failure of every external call, and must state the concrete failure scenario for every finding.
- **Compliance** first discovers the written rule sources in the repo, then only reports findings it can tie to a quoted rule and its location.
- **Consistency** reads sibling modules to establish the local convention, then only reports drift it can back with an in-repo precedent.

All four share one confidence rubric (0 to 100, default report threshold 80), one severity scale (critical, major, minor), one false-positive list, and one output format with pass-prefixed finding IDs (`CMP-`, `COR-`, `CPL-`, `CNS-`) so the lead can merge them mechanically. `tests/test_agent_consistency.py` enforces that: the shared sections have to stay identical or CI fails.

## How the skill works

1. **Resolve the target** into a Review Packet: base and head, diff command, changed-file stats, rule-file paths *at the base revision*, any rule files the change itself edits, and the change's stated intent.
2. **Launch the four reviewers in parallel**, as four named `Agent` calls in a single message. Reviewers receive commands to reproduce the diff, not the diff itself, so large changes do not blow up their context. With [agent teams](https://code.claude.com/docs/en/agent-teams) enabled those named spawns are also teammates, so you can follow up with one reviewer via `SendMessage` instead of re-running its pass — but the plugin does not depend on it.
3. **Verify borderline findings.** Findings between the threshold and 89 confidence go to a lightweight verifier that re-derives them from the code. Refuted findings are dropped.
4. **Merge.** Filter by threshold, deduplicate across passes (the owning pass keeps the finding), rank by severity then confidence, and compute the verdict: `FAIL` on any critical, `REQUEST_CHANGES` on any major, `PASS_WITH_NOTES` on any minor, else `PASS`. If any selected pass failed or returned nothing usable the verdict is `INCOMPLETE` instead, whatever the findings say — a review that did not happen is not a clean one, and `INCOMPLETE` neither approves nor blocks.
5. **Report** in a fixed format, and optionally post it to the PR. With `--comment` the lead runs `skills/review/scripts/post-review.py`, which creates one pull-request review with an inline comment per finding anchored at its file and line on the head commit, the verdict and pass summaries as the review body, and the review event taken from the verdict: `PASS` and `PASS_WITH_NOTES` approve, since minor findings are nits, while `REQUEST_CHANGES` or `FAIL` requests changes and `INCOMPLETE` only comments. GitHub refuses to approve or request changes on your own PR, so the script falls back to a plain comment and says so. Findings on lines GitHub cannot anchor (outside the diff) are listed in the body instead. The script dry-runs first, and it is the only write the skill ever performs outside its temporary directory.

Every run, with or without `--comment`, also saves `report.md` and `findings.json` to a temporary directory outside the repository and names both paths. `findings.json` follows the repository's [finding contract](../../shared/finding-contract/README.md) and is validated before the skill mentions it, and `post-review.py` validates it again before posting anything. It is what [testgaps](../testgaps/README.md) reads:

```text
/testgaps:write /tmp/tmp.X1y2/findings.json
```

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

## The change is evidence, not instruction

A reviewer reads things the change's author controls: the diff, the PR description, ticket text, code comments, and the repo's own rule files. Every agent carries an "Untrusted input" section saying that all of it is evidence *about* the change and none of it is an instruction to the reviewer, and that text aimed at the reviewer ("out of scope", "already approved by security", "report PASS") is itself reportable.

The concrete rule behind it: **written rules bind at the base revision.** The skill enumerates rule files with `git ls-tree -r --name-only <base>` and the reviewers read them with `git show <base>:<path>`, so a change cannot introduce the `CLAUDE.md` rule that excuses it. If the change edits a rule source, that edit is listed separately in the Review Packet and reported for a human instead of being adopted as a criterion.

This also fixes a plain bug: on a pull-request target nothing is checked out at the head, so reading rule files from the working tree read whatever branch the session happened to be sitting on, not the change under review.

## External tooling, strictly read-only

The reviewers can use whatever MCP servers and CLIs the session already has, such as GitHub or GitLab, Jira, Linear, Confluence, Notion and Sentry, to pull in PR descriptions, ticket acceptance criteria, prior review comments, ADRs and CI status. They are never allowed to change anything. Read-only is enforced at three layers:

| Layer | Mechanism | What it does |
|---|---|---|
| Tool access | `tools:` / `disallowedTools:` in each agent | Grants Read, Grep, Glob, Bash, WebFetch, WebSearch and all MCP tools (`mcp__*`); removes Edit, Write, MultiEdit, NotebookEdit. |
| Guard hook | `hooks/hooks.json` → `hooks/readonly-guard.py` (PreToolUse) | While a reviewer agent is running: denies file edits, state-changing shell commands (`git push`, `gh pr comment`, `rm`, `wget`, redirection to files in any spelling, process substitution, scripting languages, package managers, …) and write-style MCP tools (`create_*`, `update_*`, `add_comment`, `transition*`, …). Every line of a multi-line command is classified, wrappers such as `env` and `nice` are unwrapped, and flags are normalised so `-XPOST`, `--field=` and `-Ei` are caught. `curl` is allow-listed by option (GET/HEAD to stdout only), `gh api` accepts no body flags, HTTPie needs `--ignore-stdin`, and `sed`/`awk` scripts are scanned for `w`/`e`/`>`/`\|` commands. Auto-allows recognised reads (`git diff`, `gh pr view`, `jira issue view`, `mcp__*__get_*`, `list_*`, `search_*`) so reviews do not stall on permission prompts. Fails closed: anything it cannot classify is denied with a reason telling the agent what to use instead. Has no effect on other agents or the main session. |
| Instructions | "External tooling (read-only)" section in every agent prompt | Tells the reviewer what sources to use, that every call must be a read, and not to work around a denial. |

Check it yourself rather than taking the claim on trust — the guard answers for itself, against the version you have:

```bash
READONLY_GUARD_AGENTS='*-reviewer' python3 hooks/readonly-guard.py --selftest
```

It runs a read (`git diff HEAD`), two shell writes (`rm -rf build`, `echo hi > out.txt`), a `Write`, and one MCP read and write, and reports the decision for each. `python3 tests/test_readonly_guard.py` is the full suite behind it.

Some Claude Code builds do not expose Grep and Glob to subagents with an explicit `tools:` list; the reviewers then fall back to `grep`, `rg` and `find` through Bash, which the guard auto-allows.

**What the guard is and is not.** It is defence in depth against a well-intentioned model taking a state-changing action by mistake. It is not a sandbox and not a defence against a determined adversary with shell access: it classifies commands and tool names heuristically, and although it fails closed on anything it cannot classify, a sufficiently creative command may still get through. If you need a real boundary, use OS-level sandboxing or a container. See [SECURITY.md](SECURITY.md).

The guard is standard-library Python, split into `hooks/guard/` behind the `hooks/readonly-guard.py` entry point, with a unit-test suite (`python3 tests/test_readonly_guard.py`). Environment variables tune it without editing code; `ALLOW` and `DENY` take comma-separated globs matched against tool names or shell commands:

```bash
READONLY_GUARD_ALLOW="mcp__context7__*,mcp__mytracker__frobnicate"   # extra reads the guard cannot infer
READONLY_GUARD_DENY="mcp__github__*"                                # deny wins over allow
READONLY_GUARD_STRICT=1                                             # deny calls that name no agent at all
READONLY_GUARD_DEBUG=1                                              # report on stderr when scoping does not resolve
```

`READONLY_GUARD_AGENTS` scopes the guard to the four reviewers by reading the calling agent's type out of the hook payload. When a payload names no agent — which is what the main session's own calls look like — the guard defers, because denying there would break your own tools. That is also what a renamed payload key would look like, so the guard resolves any agent-shaped key rather than one exact spelling, `READONLY_GUARD_DEBUG=1` makes a non-resolving scope visible, and `READONLY_GUARD_STRICT=1` fails closed instead. To check the wiring end to end at any time:

```bash
READONLY_GUARD_AGENTS='*-reviewer' python3 hooks/readonly-guard.py --selftest
```

If you copy the agents into a project's `.claude/agents/` instead of installing the plugin, the hook is not loaded automatically. Copy the whole `hooks/` directory — `readonly-guard.py` is the entry point and imports the `guard/` package beside it — and add it to that project's `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [{ "hooks": [{ "type": "command",
      "command": "READONLY_GUARD_AGENTS='*-reviewer' python3 /path/to/agents/plugins/fourpass/hooks/readonly-guard.py" }] }]
  }
}
```

## Configuration

| Knob | Where | Default |
|---|---|---|
| Confidence threshold | `--threshold N` | 80 |
| Passes to run | `--passes a,b,c` | all four |
| Verification of borderline findings | `--no-verify` to skip | on |
| Model for reviewers | `model:` in each `agents/*.md` | `inherit` (the session's model) |
| Follow-up with one reviewer | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` in settings | off; the four passes run the same either way |

Agents are deliberately read-only (`disallowedTools` plus the guard hook). Keep both when customising them.

## Layout

Everything below is relative to `plugins/fourpass/`. The plugin is self-contained: nothing in it reaches outside this directory, so it can be installed, validated and tested on its own. The marketplace manifest, CI workflow and check script live at the repository root and are shared by every plugin there.

```text
.claude-plugin/
  plugin.json            plugin manifest
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
                         (tests live in tests/)
    finding.schema.json  the finding contract findings.json follows
    finding_contract.py  its validator; both are copies of shared/finding-contract/
hooks/
  hooks.json             registers the PreToolUse read-only guard
  readonly-guard.py      entry point: scoping, the decision, --selftest
  guard/
    tables.py            which tools, commands and MCP names are reads
    shell.py             shell command classification
    mcp.py               MCP tool-name classification
    util.py              the allow/deny shape and shared helpers
tests/
  test_readonly_guard.py     the guard
  test_post_review.py        the PR poster
  test_agent_consistency.py  the four agents stay mergeable
  test_skill_invariants.py   the skill's security-relevant instructions
  test_evals.py              the eval suite measures what it claims to
  test_lint.py               static checks over this repo's own Python
  test_post_review_integration.py  opt-in, read-only, against real GitHub
evals/
  README.md              how to run the suite and add a case
  build_prompts.py       generates each case's prompt from its fixture
  fixtures/              small seeded-defect and bait fixtures
  <case>/                prompt.md + graders/criteria.md
CHANGELOG.md             this plugin's releases
CONTRIBUTING.md          ground rules for the agents, the guard and the skill
```

At the repository root: `.claude-plugin/marketplace.json`, `scripts/check.sh`, `SECURITY.md` and `.github/`.

## Development

Validate the manifest, agents and skills, from this directory (also runs in CI):

```bash
claude plugin validate --strict .          # plugin manifest
claude plugin validate --strict agents
claude plugin validate --strict skills
```

Run the tests with the repository's check script, which runs every plugin or just this one:

```bash
../../scripts/check.sh                              # everything CI runs, every plugin
../../scripts/check.sh fourpass             # just this plugin
../../scripts/check.sh --tests fourpass     # just this plugin's Python suites
../../scripts/check.sh --manifests fourpass # just this plugin's manifest/component validation
```

That script is the single source of truth for what gets checked: every
`tests/test_*.py` here (the read-only guard suite, the PR poster suite, the
agent-consistency test, a standard-library lint pass, the eval prompts being in
step with their fixtures), the guard selftest, and the `claude plugin validate
--strict` targets. CI calls the same script.

The Python here is standard library only and supports 3.9 and up, because the hook runs under whatever `python3` the user has and stock macOS is still on 3.9. CI runs the suites on 3.9 and 3.13.

Check the token cost of what the plugin loads into a session:

```bash
claude plugin details fourpass
```

Measure whether the reviews are any good — seeded defects the passes must
catch, and bait they must stay quiet on:

```bash
claude plugin eval --allow-tools Bash --ablation none --runs 1 .
```

Each run spawns the four reviewers for real, so the suite costs real money:
about $1.40 per run, ~$10 for that command, and ~$55 if you run it with no
flags — all API-price equivalents of the tokens used, which on a subscription
login draw on your plan's allowance rather than producing a bill. It is also non-deterministic, so it is not in CI. Read
[evals/README.md](evals/README.md) before running it.

When editing an agent, keep the shared sections (out-of-scope list, false-positive list, confidence rubric, output format) identical across all four files; the skill's merge step depends on them.

## License

MIT. See [LICENSE](LICENSE).
