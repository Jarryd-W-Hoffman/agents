# testgaps

A Claude Code plugin that turns code-review findings into tests. For each finding, a `test-writer` agent writes the smallest test that proves it, in the repository's own test conventions, runs that file, and reports what the result means. A hook confines the writer to test files, so it cannot "fix" the code to make its test pass.

It pairs with [fourpass](../fourpass/README.md), reading the `findings.json` it saves beside every report, but any findings list in the repository's [finding contract](../../shared/finding-contract/README.md) works, and so does a one-line request.

## What it is for

A review finding is an opinion with a confidence number. A failing test is a fact. The writer turns the first into the second:

| Finding says | The writer produces | Outcome it reports |
|---|---|---|
| This code is wrong (a correctness finding) | A test that fails on the current code for the reason the finding gives | `REPRODUCED`, or `NOT_REPRODUCED` with the writer's view on whether the finding or the test is wrong |
| This code is untested (a completeness finding) | A test that passes and exercises the behaviour the change claims to add | `COVERED` |
| Either, but the change intent does not say what the behaviour should be | Nothing. Pinning behaviour nobody decided is a liability | `NOT_WRITTEN`, with the reason |

A test that could not run to a verdict is `BLOCKED`, with the error. The outcome column is the point of the tool: a correctness finding that no test can be made to fail is a false positive, found by execution rather than by a second reading.

## Installation

**Try it without installing** (loads for one session):

```bash
claude --plugin-dir /path/to/agents/plugins/testgaps
```

**Install from this repo as a local marketplace:**

```text
/plugin marketplace add /path/to/agents
/plugin install testgaps@jarrydh-agents
```

**Or copy the pieces into a project** (no namespace prefix), from this plugin's directory:

```bash
cd plugins/testgaps
cp agents/test-writer.md    your-project/.claude/agents/
cp -r skills/write    your-project/.claude/skills/
cp -r hooks                 your-project/.claude/testgaps-hooks/
```

Copying the pieces does not bring the write-scope guard with them: it is registered by the plugin's `hooks.json`, which only the plugin install reads. Wire it up by hand as shown under [the write-scope guard](#the-write-scope-guard).

Restart Claude Code after installing. The agent appears in `/agents`; the skill appears as `/testgaps:write` (or `/write` when copied into a project).

## Usage

```text
/testgaps:write review.md                     # every correctness and completeness finding in a four-pass report
/testgaps:write review.md --only COR-1,CMP-2  # just those
/testgaps:write review.md --all-passes        # include every other pass too (compliance, consistency, migrations, ...)
/testgaps:write findings.json --max 4         # the finding contract fourpass saves on every run
/testgaps:write "export_row crashes when invoice.customer is None, billing/exporter.py:7"
/testgaps:write review.md --runner "npm run test:unit"
```

The skill is the lead: it resolves the findings, works out once how this repository runs its tests and where they live, launches one `test-writer` per finding in parallel (findings on the same file run in sequential waves, so the second writer extends the first one's file), then checks `git status` for anything written outside test paths and merges the outcomes into one report. It never commits and never posts anywhere.

The agent can also be invoked on its own:

```text
Use the test-writer agent to reproduce the null-customer bug in billing/exporter.py as a failing test.
```

## What the report looks like

```markdown
# Test-gap writer: PR 142

**Written:** 1 file, 3 tests · **Ran:** `python -m pytest tests/billing/test_exporter.py -q`
**Source files touched:** none

| Finding | Test | Outcome | Result | Meaning |
|---|---|---|---|---|
| COR-1 | `tests/billing/test_exporter.py::test_export_row_handles_invoice_with_no_customer` | REPRODUCED | FAIL · `AttributeError: 'NoneType' object has no attribute 'email'` | Reproduces the defect. Should pass once the fix lands. |
| CMP-1 | `tests/billing/test_exporter.py::test_export_row_renders_id_email_and_total` | COVERED | PASS | Covers the happy path the change claims to add. |

## Assumptions
- The empty-customer row renders as an empty email column. If the fix skips those invoices instead, change the COR-1 test to assert on omission.

## Not written
- Nothing for `total` formatting: the intent does not say whether `120.0` or `120.00` is wanted.

## Next
The failing test is a regression suite for COR-1. Apply the fix and re-run the file.
```

## The write-scope guard

The guard is the mirror of fourpass's read-only guard. While a `test-writer` agent is running, it decides every tool call:

| Call | Decision |
|---|---|
| `Edit`, `Write`, `MultiEdit`, `NotebookEdit` on a test path | allow |
| The same on any other path, or a path that escapes the session directory | deny, with the path named |
| `Write` onto a file that already exists, test path or not | deny: extend it with `Edit`. A whole-file write is how one writer erases another's test, or an existing one |
| Shell reads (`git diff`, `git log`, `ls`, `cat`, `grep`, `rg`, `find`, …) | allow |
| Recognised test runners (`pytest`, `python -m pytest`, `npm test`, `npx jest`, `go test`, `cargo test`, `mvn test`, `dotnet test`, `phpunit`, `rspec`, `mix test`, `make test`, …) | allow |
| Anything else: redirects to files, process substitution, `python -c`, `pip install`, `curl`, `rm`, `sed -i`, `git commit`, `make build`, every MCP tool | deny, with a reason |

A test path is one with a directory segment such as `tests`, `test`, `__tests__`, `spec`, or a basename in a recognised test pattern (`test_*.py`, `*_test.go`, `*.test.ts`, `*Test.php`, `*_spec.rb`, …). The guard fails closed: anything it cannot classify is denied. It has no effect on other agents or the main session, which is scoped by `TEST_SCOPE_GUARD_AGENTS` in `hooks/hooks.json`.

Environment variables tune it without editing code, each a comma-separated list of globs:

| Variable | Matched against | Effect |
|---|---|---|
| `TEST_SCOPE_GUARD_PATHS` | the repo-relative path | more paths count as test paths (e.g. `src/**/__snapshots__/*`) |
| `TEST_SCOPE_GUARD_RUNNERS` | each simple shell command | more commands count as test runners (e.g. `tox *`, `./bin/test *`) |
| `TEST_SCOPE_GUARD_ALLOW` | tool names or shell commands | allowed outright |
| `TEST_SCOPE_GUARD_DENY` | tool names or shell commands | denied outright; wins over everything |
| `TEST_SCOPE_GUARD_STRICT=1` | | deny calls whose payload names no agent, instead of deferring |
| `TEST_SCOPE_GUARD_DEBUG=1` | | report on stderr when the scope is set but the payload names no agent |

Check the wiring:

```bash
TEST_SCOPE_GUARD_AGENTS='*test-writer' python3 hooks/test-scope-guard.py --selftest
```

If you copy the agent into a project's `.claude/agents/` instead of installing the plugin, copy `hooks/` too and register it in that project's `.claude/settings.json`:

```json
{ "hooks": { "PreToolUse": [ { "hooks": [ { "type": "command",
      "command": "TEST_SCOPE_GUARD_AGENTS='*test-writer' python3 /path/to/agents/plugins/testgaps/hooks/test-scope-guard.py" }] }] } }
```

**What the guard is not.** It constrains the agent's tool calls. A test runner executes the project's code, and that code can do whatever the project's own test suite can. The guard is defence in depth against a well-intentioned model making a mistake, not a sandbox; see the repository's [SECURITY.md](../../SECURITY.md).

## Layout

Everything below is relative to `plugins/testgaps/`. The plugin is self-contained.

```text
.claude-plugin/
  plugin.json              plugin manifest
agents/
  test-writer.md           one finding in, one proven test out
skills/write/
  SKILL.md                 the orchestrating skill
  references/
    writer-brief.md        the brief sent to each writer
    report-template.md     the merged report format
  scripts/
    extract-findings.py    parses a four-pass report into findings JSON (the fallback
                           when no findings.json sits beside the report)
    finding.schema.json    the finding contract findings JSON must follow
    finding_contract.py    its validator; both are copies of shared/finding-contract/
hooks/
  hooks.json               registers the PreToolUse write-scope guard
  test-scope-guard.py      the guard: path rules, runner allow-list, --selftest
tests/
  test_test_scope_guard.py   the guard
  test_extract_findings.py   the report parser
  test_skill_invariants.py   the skill's and agent's security-relevant settings
  test_lint.py               static checks over this plugin's Python
CHANGELOG.md
CONTRIBUTING.md
```

## Development

From this directory:

```bash
claude plugin validate --strict .
claude plugin validate --strict agents
claude plugin validate --strict skills
../../scripts/check.sh testgaps     # everything CI runs for this plugin
```

Standard-library Python, 3.9 and up, for the same reason as the sibling plugin: the hook runs under whatever `python3` the user has.

There is no eval suite yet. The right one is a fixture repository with a seeded defect and a finding, graded on whether the writer reports `REPRODUCED` and touches no source file; it needs `claude plugin eval` to scaffold a real git checkout, which did not work on the CLI version this was built with. See the sibling's `evals/README.md` for the probe.
