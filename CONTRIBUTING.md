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
tools: Read, Grep, Glob, Bash    # Bash is for read-only git/gh inspection only
disallowedTools: Edit, Write, MultiEdit, NotebookEdit
model: inherit
color: <one distinct colour per agent>
```

Agents are read-only by design. Do not grant write tools.

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
```

Then load the plugin in a session and confirm the agents and skill appear:

```bash
claude --plugin-dir . -p "List the agent types and skills provided by the four-pass-review plugin." --max-turns 1
```

Add an entry under `[Unreleased]` in `CHANGELOG.md` and bump `version` in `.claude-plugin/plugin.json` on release.
