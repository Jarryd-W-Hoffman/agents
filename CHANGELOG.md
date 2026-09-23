# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Reviewer agents can now use external tooling (MCP servers such as GitHub, Jira, Linear, Confluence, Sentry; CLIs such as `gh`, `glab`, `jira`, `linear`; WebFetch/WebSearch) to gather context.
- `hooks/readonly-guard.py`: a PreToolUse guard, registered in `hooks/hooks.json`, that keeps the four reviewer agents strictly read-only. Denies edits, state-changing shell commands and write-style MCP tools; auto-allows recognised reads; fails closed. Tunable with `READONLY_GUARD_ALLOW` / `READONLY_GUARD_DENY`. Unit tests in `hooks/test_readonly_guard.py`.
- "External tooling (read-only)" section in every agent prompt; the review skill now lists available context sources in the Review Packet.

## [0.1.0] - 2026-09-24

### Added
- `completeness-reviewer` agent: checks that everything the change should contain is present.
- `correctness-reviewer` agent: checks that the code that is present behaves as intended.
- `compliance-reviewer` agent: checks the change against explicit written rules (CLAUDE.md, policies, ADRs, licences, regulatory).
- `consistency-reviewer` agent: checks the change against the implicit conventions of the surrounding codebase.
- `review` skill: resolves a review target, runs the four reviewers in parallel (agent teams or parallel subagents), verifies borderline findings, and merges everything into one ranked report.
- Plugin manifest, local marketplace manifest, and CI validation workflow.
