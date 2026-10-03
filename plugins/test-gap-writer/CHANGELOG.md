# Changelog

All notable changes to this plugin are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this plugin adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Findings JSON is validated against the finding contract** (`skills/write-tests/scripts/finding.schema.json`, checked by `finding_contract.py`) instead of checking for `id`, `path` and `line` by eye. An invalid file is refused with its errors, not repaired.
- **Given a report, the skill uses the `findings.json` saved beside it** when there is one, which four-pass-review now does on every run, and reads the report only for its header. Parsing the markdown is the fallback, because the report's layout belongs to another plugin and may change.
- `extract-findings.py` validates what it parsed against the contract and exits 1 when it breaks it. It parses hyphenated pass names (`migration-safety`), and a finding heading with no body takes its title as the body, which the contract requires.

### Added

- `test-writer` agent: takes one review finding, writes the smallest test that proves it in the repository's own test conventions, runs that file, and reports one of five outcomes: `REPRODUCED` (the test fails for the reason the finding gives), `COVERED` (it passes and exercises the behaviour the finding called untested), `NOT_REPRODUCED` (a test aimed at a correctness finding passes, with the writer's view on whether the finding or the test is wrong), `BLOCKED` (written but could not run to a verdict) or `NOT_WRITTEN` (with the reason). It adds tests only; it never edits source, never weakens an existing test, never commits.
- `write-tests` skill: takes a four-pass-review report, a `findings.json`, or a one-line request; selects the correctness and completeness findings by default; launches one `test-writer` per finding in parallel, with findings on the same file run in sequential waves so a later writer extends the earlier one's test file instead of racing it; then checks `git status` for anything written outside test paths and merges the outcomes into one report. `scripts/extract-findings.py` parses the four-pass merged report into the finding contract.
- `hooks/test-scope-guard.py`, the write-scope guard: while a `test-writer` agent is running, allows `Edit`, `Write`, `MultiEdit` and `NotebookEdit` only on test paths, and denies `Write` onto a file that already exists, so a writer can extend a test file but never replace one (resolved against the session directory, so `..` and absolute paths elsewhere are denied), allows shell reads and recognised test runners, and denies everything else: redirects to files, process substitution, interpreters with inline code, package installs, `rm`/`mv`/`cp`/`sed -i`, state-changing `git`, and all MCP tools. Fails closed on anything it cannot classify; scoped by `TEST_SCOPE_GUARD_AGENTS` so it never touches other agents or the main session. `--selftest` checks the wiring.
- Tests: the guard suite, the report parser suite, skill invariants, and a standard-library lint pass.
