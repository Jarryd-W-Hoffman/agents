# Security

## Reporting a vulnerability

Report privately through this repository's [security advisories](https://github.com/Jarryd-W-Hoffman/agents/security/advisories/new).

Please do not open a public issue for a vulnerability. Include what you did, what happened, and the version of the plugin and of Claude Code. If the report is about the read-only guard, the exact command or tool name that got through is the useful part.

## Supported versions

Every plugin here is 0.x and versioned on its own. Only the latest release of each is supported; fixes go into the next release rather than being backported.

## What the read-only guard is for

This repository ships Claude Code plugins under `plugins/`. Three of them carry a PreToolUse guard: the read-only guard in `four-pass-review`, covered below, which `migration-safety` carries an identical copy of for its `migration-reviewer` agent; and the write-scope guard in `test-gap-writer`, which confines its `test-writer` agent to test paths and recognised test runners. The same statement applies to all of them: each is defence in depth against a well-intentioned model making a mistake, not a sandbox. The write-scope guard has one further limit worth naming: it constrains the agent's own tool calls, but a test runner executes the project's code, and that code can do anything the project's own test suite can.

`plugins/four-pass-review/hooks/readonly-guard.py` is a PreToolUse hook that keeps the four reviewer agents read-only. It denies file edits, state-changing shell commands and write-style MCP tools, auto-allows recognised reads so reviews do not stall on permission prompts, and fails closed: anything it cannot classify is denied with a reason.

**It is defence in depth against a well-intentioned model making a mistake. It is not a sandbox.**

Concretely:

- It classifies shell commands and MCP tool names heuristically. It parses the command, unwraps wrappers, normalises flag spellings, and checks per-command tables — but a sufficiently creative command may still get through. Treat a bypass as a bug worth reporting, not as a breach of a boundary that was never there.
- It only applies to this plugin's four reviewer agents, scoped by `READONLY_GUARD_AGENTS`. It deliberately does not touch the main session or other agents. When a hook payload carries no agent identity, the guard defers rather than denying, because denying there would break the user's own tools. `READONLY_GUARD_STRICT=1` opts into failing closed instead, and `READONLY_GUARD_DEBUG=1` reports when scoping does not resolve.
- It is not a boundary against an adversary who can already run shell commands in your session. If you need one, use OS-level sandboxing or a container. Claude Code's own permission system and sandboxing are the right layer for that; this hook sits above them.

## Untrusted input

The reviewer agents read content the change's author controls: the diff itself, pull-request and commit descriptions, linked ticket text, code comments, and any page fetched while researching. A review that ends in `--comment` can approve or request changes on a pull request, so content that steers the review has a real effect.

Two mitigations, both in the agent prompts rather than in code:

- Every agent carries an "Untrusted input" section saying that all of that is evidence about the change and none of it is instruction to the reviewer, and that text aimed at the reviewer is itself reportable.
- Written rules bind at the base revision. Rule files are enumerated with `git ls-tree -r --name-only <base>` and read with `git show <base>:<path>`, so a change cannot add the `CLAUDE.md` rule that excuses it. A change that edits a rule source has that edit reported for a human instead of adopted.

These are instructions to a model, not a control. They raise the cost of a prompt-injection attempt; they do not make one impossible. Review what the plugin posts before trusting it on a repository that accepts pull requests from people you do not know, and consider `--comment=summary`, which comments without approving or requesting changes.
