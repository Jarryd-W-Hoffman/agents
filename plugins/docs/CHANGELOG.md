# Changelog

All notable changes to this plugin are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this plugin adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `readme` skill: surveys the repository, plans the sections, diagrams, pseudocode and screenshots, takes the screenshots, writes `README.md` in the shape of Kite's, and checks it. `--update` keeps the existing structure; `--no-screenshots` reuses what is there; `--url` uses an app that is already running.
- `manual` skill: plans one chapter per feature area, takes the screenshots, writes the manual's index, runs one `manual-writer` per chapter in parallel (eight at a time), checks the result, sends chapters with errors back to their writer, and links the manual from the README. Takes chapter slugs to write or redo only those.
- `screenshots` skill: retakes every shot in `docs/screenshots.json`, or the named ones, or adds a new one with `--add`.
- `manual-writer` agent: writes one chapter from the code, confirming every statement, and replies with what it could not confirm, the screenshots it wanted and the changes it suggests elsewhere. No shell.
- `hooks/docs-scope-guard.py`: while a `*manual-writer` runs, allows Edit and Write only on Markdown under `docs/`, and denies the shell, MultiEdit, NotebookEdit, web tools and MCP tools. Fails closed. `--selftest` is run by `scripts/check.sh`.
- `scripts/survey.py`: name, GitHub slug, stacks (PHP, Node, Go, Python, Rust, Godot) and their commands, CI workflows with badge Markdown, licence, existing docs and images, and what there is to screenshot (web, desktop, CLI, game; seeders; browser tests).
- `scripts/shoot.mjs`: page shots (login once, actions, window or element, light or dark, local storage) and terminal shots (a real command, ANSI colours, in a terminal window) from a plan; `--check` validates the plan without a browser; `--only` takes some.
- `scripts/docs_check.py`: errors for missing images, missing alt text, broken links and anchors (GitHub's slug rules), empty, unknown or unbalanced Mermaid diagrams, chapters without a screenshot or diagram or missing from the index, a README that does not link its manual, and planned shots not taken. Warnings for drift from the template.
- `references/`: the README and manual templates, the house style (voice, formatting, diagrams, pseudocode, screenshots, accuracy), the screenshot guide and the writer brief, distilled from Kite.
- Tests: the check, the survey, the screenshot plan and ANSI rendering (needs Node, skipped without it), the skill and agent invariants, and a standard-library lint pass.
- `shoot.mjs`: `"render": "markdown"` draws a terminal shot's output as Markdown, the way Claude Code shows a report; `--cached` redraws terminal shots from their last output without running the command again.
- `survey.py` recognises a Claude Code plugin or marketplace, listing each plugin's commands, agents and hooks, and gives it terminal shots.

### Fixed

- `survey.py` no longer reports a workflow as a release workflow because a comment mentions "release". Found by running `/docs:readme` on this repository.
