# Contributing

## Ground rules for the four reviewer agents

The `review` skill merges the four reports mechanically, so the agents must stay aligned. When you edit one, keep these sections **identical** across all four files in `agents/`:

- the shared "Do not report" list (pre-existing issues, linter-caught issues, nitpicks, intentional changes, silenced issues, speculation)
- the confidence rubric (0–25, 26–50, 51–79, 80–89, 90–100; default threshold 80)
- the severity meanings and the verdict rule (FAIL on any critical, PASS_WITH_NOTES on any other finding, else PASS)
- the output format: header block, `### Findings`, one `#### [PREFIX-n]` block per finding with Severity, Confidence, Location, Evidence, Why it matters, Suggested fix, then `### Notes`

Pass-specific additions to the format are limited to what each file already declares: correctness adds a **Failure scenario** bullet; compliance adds a **Rule sources consulted** line after the summary.

Finding ID prefixes are fixed: `CMP` (completeness), `COR` (correctness), `CPL` (compliance), `CNS` (consistency).

## Scope boundaries

Each agent answers exactly one question and names the other three as out of scope. Do not let a pass grow into a neighbour's territory; if a check belongs to two passes, give it to the owner below and reference it from the other.

| Question | Owner |
|---|---|
| Is something missing? | completeness |
| Is the code that is here wrong? | correctness |
| Does it break a rule that is written down? | compliance |
| Does it diverge from what the surrounding code does? | consistency |

## Frontmatter

```yaml
name: <pass>-reviewer            # lowercase-hyphen, matches the filename
description: >-                  # starts "Use this agent when …", includes 2–3 <example> blocks
tools: Read, Grep, Glob, Bash, ToolSearch, WebFetch, WebSearch, ListMcpResourcesTool, ReadMcpResourceTool, mcp__*
disallowedTools: Edit, Write, MultiEdit, NotebookEdit
model: inherit
color: <one distinct colour per agent>
```

Agents are read-only by design. Do not grant write tools. External tooling is allowed through `WebFetch, WebSearch, ListMcpResourcesTool, ReadMcpResourceTool, mcp__*` in `tools:`, and the guard hook in `hooks/` is what keeps those reads only.

## The read-only guard

`hooks/readonly-guard.py` runs on every PreToolUse event while a reviewer agent is active (scoped via `READONLY_GUARD_AGENTS` in `hooks/hooks.json`). When you change it:

- Keep it standard-library only and fail-closed: unknown commands and unclassifiable MCP tools are denied with a reason.
- Add a test for every new allow or deny case in `hooks/test_readonly_guard.py` and run `python3 hooks/test_readonly_guard.py`.
- Prefer adding a CLI to the per-tool tables (`GIT_*`, `GH_READONLY`, `GLAB_READONLY`) over widening the generic verb lists.
- Never auto-allow anything that can send data or write to disk.

## Style

- Second person, imperative. `##` headings. 120–220 lines per agent.
- Language-agnostic; give language-specific examples only as "e.g.".
- No emojis. No filler.

## Before opening a PR

```bash
claude plugin validate --strict .
claude plugin validate --strict .claude-plugin/plugin.json
claude plugin validate --strict agents
claude plugin validate --strict skills
python3 hooks/test_readonly_guard.py
```

Then load the plugin in a session and confirm the agents and skill appear:

```bash
claude --plugin-dir . -p "List the agent types and skills provided by the four-pass-review plugin." --max-turns 1
```

Add an entry under `[Unreleased]` in `CHANGELOG.md` and bump `version` in `.claude-plugin/plugin.json` on release.
