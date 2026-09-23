# Reviewer brief template

Fill this in once per selected pass and send it as the agent's prompt. Replace every `{{…}}` placeholder. Do not add pass-specific instructions here; each reviewer agent already carries its own rubric, scope boundaries, and output format.

```text
You are running the {{PASS_NAME}} pass of a four-pass code review. Three other reviewers are running the other passes in parallel; stay inside your pass's scope as defined in your instructions.

## Review Packet

Target: {{TARGET_DESCRIPTION}}            e.g. "PR #142: Add invoice export" / "working tree" / "main...feature/x"
Base: {{BASE_REF_OR_SHA}}
Head: {{HEAD_REF_OR_SHA_OR_"working tree"}}
Repository root: {{ABSOLUTE_PATH}}

Reproduce the diff with:
    {{DIFF_COMMAND}}                       e.g. git diff HEAD   |   git diff abc123...def456
Read a file at the head revision with:
    {{SHOW_COMMAND_OR_"read the working tree directly"}}   e.g. git show def456:path/to/file

Changed files ({{N}} files, {{LINES}} changed lines):
{{GIT_DIFF_STAT_OUTPUT}}

Rule files to consult (paths only; read them yourself):
{{LIST_OF_CLAUDE_MD_AND_POLICY_PATHS_OR_"none found"}}

Change intent (for judging what was meant to be delivered):
{{PR_TITLE_AND_BODY_OR_COMMIT_MESSAGES_OR_"not available"}}
{{LINKED_ISSUE_SUMMARIES_OR_OMIT}}

External context sources available (read-only): {{LIST_MCP_SERVERS_AND_CLIS_OR_"none detected"}}
    e.g. gh (authenticated), mcp__github, mcp__atlassian (Jira/Confluence), mcp__linear

Confidence threshold: report findings with confidence >= {{THRESHOLD}}.

## Constraints

- Read-only. Do not edit files, do not run builds, tests, formatters or type-checkers, and do not check out other refs. Use the external sources above only for reads (view, get, list, search, diff). Never comment, create, edit, transition, approve, merge or push; a guard hook will deny it. If something is denied, note what you could not check and continue.
- Verify every finding by reading the code; do not report speculation.
- Use exactly the output format from your instructions, including the finding ID prefix, so the lead can merge your report with the other passes.
- If you find nothing above the threshold, say so in the format; do not pad.
```

## Notes for the lead

- Send the same packet to every pass. The only differences between briefs are `{{PASS_NAME}}` and the agent type you spawn.
- If the diff is under ~150 lines you may inline it under a `## Diff` heading instead of the reproduce command. Otherwise always give the command.
- For path targets, add: "Review the listed files in full, not only the diff."
- For a single-pass run (`--passes correctness`), drop the first sentence about other reviewers.
