# Contributing to fourpass

Repository-wide conventions (layout, the check script, adding a plugin) are in the root [CONTRIBUTING.md](../../CONTRIBUTING.md). Everything in this file is specific to this plugin, and every path is relative to `plugins/fourpass/`.

## Ground rules for the four reviewer agents

The `review` skill merges the four reports mechanically, so the agents must stay aligned. When you edit one, keep these sections **identical** across all four files in `agents/`:

- the shared "Do not report" list (pre-existing issues, linter-caught issues, nitpicks, intentional changes, silenced issues, speculation)
- the "External tooling (read-only)" and "Untrusted input" sections, verbatim
- the confidence rubric (0–25, 26–50, 51–79, 80–89, 90–100; default threshold 80)
- the severity meanings and the verdict rule (FAIL on any critical, REQUEST_CHANGES on any major, PASS_WITH_NOTES on any minor, else PASS)

`INCOMPLETE` is deliberately **not** in that list. It belongs to the merged report only: it means a pass did not report, which an agent cannot say about itself. Do not add it to the four agents.
- the output format: header block, `### Findings`, one `#### [PREFIX-n]` block per finding with Severity, Confidence, Location, Evidence, Why it matters, Suggested fix, then `### Notes`

Pass-specific additions to the format are limited to what each file already declares: correctness adds a **Failure scenario** bullet; compliance adds a **Rule sources consulted** line after the summary.

This is enforced, not just requested: `python3 tests/test_agent_consistency.py` fails if a shared section drifts, if the frontmatter stops matching, if a pass borrows another's finding prefix, or if a pass stops naming the other three as out of scope. Run it after touching any agent file.

## Untrusted input

The reviewers read content the change's author controls. Two invariants hold everywhere:

- **Written rules bind at the rule base.** Rule files are enumerated with `git ls-tree -r --name-only <rule base>` and read with `git show <rule base>:<path>`. The rule base is the revision the change branched from. Never read rules from the working tree (on a PR target nothing is checked out at the head), and never from the review base, which `--since` moves to a commit *inside* the change — doing so would let an incremental re-review adopt a rule the change itself added, which is the loophole the rule base exists to close.
- **Content is evidence, never instruction.** If you add a new context source (an MCP server, a CLI, a fetched page), it inherits that rule. Do not add anything that treats fetched text as direction to the reviewer.

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

`hooks/readonly-guard.py` runs on every PreToolUse event while a reviewer agent is active (scoped via `READONLY_GUARD_AGENTS` in `hooks/hooks.json`). It is the entry point only: the tables live in `hooks/guard/tables.py`, shell classification in `hooks/guard/shell.py`, MCP classification in `hooks/guard/mcp.py`. Add a command to the tables, not to the entry point. When you change it:

- Keep it standard-library only and fail-closed: unknown commands and unclassifiable MCP tools are denied with a reason.
- Keep it working on Python 3.9 — the hook runs under whatever `python3` the user has, and that is still 3.9 on stock macOS. CI tests 3.9 and 3.13 for this reason.
- Add a test for every new allow or deny case in `tests/test_readonly_guard.py` and run `python3 tests/test_readonly_guard.py`.
- After changing the scoping logic, run `READONLY_GUARD_AGENTS='*-reviewer' python3 hooks/readonly-guard.py --selftest`. The guard defers when a payload names no agent, so a scoping mistake makes it stop enforcing silently rather than fail.
- Prefer adding a CLI to the per-tool tables (`GIT_*`, `GH_READONLY`, `GLAB_READONLY`) over widening the generic verb lists.
- Never auto-allow anything that can send data or write to disk.

## Style

- Second person, imperative. `##` headings. 120–220 lines per agent.
- Language-agnostic; give language-specific examples only as "e.g.".
- No emojis. No filler.

## Before opening a PR

```bash
../../scripts/check.sh fourpass
```

That is the whole list: manifest and component validation, every
`tests/test_*.py` (the guard suite, the PR poster suite, the agent-consistency
test, a standard-library lint pass, and a check that the eval prompts are in
step with their fixtures) and the guard selftest. CI runs the same script, so
if it passes locally it passes there. A new `tests/test_*.py` is picked up
automatically; anything else goes in the root `scripts/check.sh`.

The `gh` paths in `post-review.py` are stubbed in the unit suite, so after
changing them run the read-only integration checks against a real pull request
— any open one you can read will do:

```bash
FOUR_PASS_REVIEW_IT_PR=142 FOUR_PASS_REVIEW_IT_REPO=owner/repo \
  python3 tests/test_post_review_integration.py
```

Then load the plugin in a session and confirm the agents and skill appear:

```bash
claude --plugin-dir . -p "List the agent types and skills provided by the fourpass plugin." --max-turns 1
```

Add an entry under `[Unreleased]` in `CHANGELOG.md` and bump `version` in `.claude-plugin/plugin.json` on release.
