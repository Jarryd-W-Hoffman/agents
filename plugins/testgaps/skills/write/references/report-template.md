# Merged report template

Use this structure verbatim. One row per test the writers wrote or declined to write. Keep each cell short; the writer's full output is available on request.

```markdown
# Test-gap writer: {{TARGET_DESCRIPTION}}

**Written:** {{N}} files, {{M}} tests · **Ran:** `{{RUNNER_COMMAND}}`
**Findings:** {{SELECTED}} of {{TOTAL}} selected{{ · skipped: <ids and why> | omit if none}}
**Source files touched:** {{none | list of paths}}

| Finding | Test | Outcome | Result | Meaning |
|---|---|---|---|---|
| {{ID}} | `{{path}}::{{test_name}}` | {{REPRODUCED \| COVERED \| NOT_REPRODUCED \| BLOCKED \| NOT_WRITTEN}} | {{FAIL · `key error line` \| PASS \| error \| —}} | {{one sentence}} |

## Assumptions

- **{{ID}}:** {{what the test assumes the intent means, and what to change if the assumption is wrong}}

## Not written

- **{{ID}}:** {{reason: behaviour unspecified / needs infrastructure / outside write scope / guard denied `path`}}

## Source files touched

{{none | one bullet per non-test path that changed, with "this should not have happened; review and revert it yourself"}}

## Next

- {{Which failing tests are the regression suite for which findings, and what to do with them: apply the fix for COR-1, re-run `path`, expect all green}}
- {{NOT_REPRODUCED findings: decide whether the finding or the test is wrong, with the writer's view}}
```

## Rules

- Rows are in the order the findings were selected: severity (critical, major, minor), then confidence descending, then path. A finding that produced several tests gets one row per test, adjacent.
- `Result` quotes the runner's key line verbatim for a failure (the exception or assertion message, not the traceback). For a pass it is `PASS`. For BLOCKED it is the error that stopped the run. For NOT_WRITTEN it is `—`.
- `Meaning` is the writer's one sentence, not yours. For NOT_REPRODUCED it must say which the writer believes: the finding is wrong, or the test does not reach the defect.
- `Source files touched` is computed from `git status --short` and `git diff --stat` after every writer has returned, not from what the writers reported. Any changed path that is not a test path goes here. Do not revert it; say that it should not have happened and that the user should review it. `none` is the expected value, and the header line carries it so a reader sees it first.
- Omit `## Assumptions`, `## Not written` and the body of `## Source files touched` when empty, but keep the header line's `Source files touched:` field always.
- Never commit, stage or post anything. The report is the whole output.
- No emojis. No praise section unless the user asks for one.
