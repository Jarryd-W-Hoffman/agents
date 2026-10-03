# Changelog

All notable changes to this plugin are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this plugin adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **The read-only guard (the copy of four-pass-review's) denies git options that run a command.** `git grep -O<cmd>` (`--open-files-in-pager`) and `--upload-pack` on `git fetch` and `git ls-remote` run the command they are given, and `git cat-file --filters` runs configured filters; all were auto-allowed as reads. Denied options are now also matched by prefix, because git accepts any unambiguous abbreviation of a long option: `git grep --textc`, `git fetch --for` and `git grep --open=<cmd>` got past the exact-name checks.

### Added

- `regression-reviewer` agent: reads each fix and revert the scan found, states the invariant it established, and checks the change against it at the head, following moved code. Reports a fix's guard removed or bypassed, reverted code re-introduced while the revert's cause still holds, a regression test removed or loosened, and a usual partner file left behind. Every finding names its earlier commit; fixes found intact are listed as kept.
- `hunt` skill: resolves the working tree, a ref range or a PR; runs the history scan and stops without launching anything when the history has nothing to say; runs one reviewer; writes the report and a validated `findings.json` with `REG-` IDs.
- `scripts/history-scan.py`: per changed file, at the base, the commits that last touched the changed lines (`git log -L`), fixes and reverts with issue references and reverted SHAs, and usual partner files missing from the change.
- The read-only guard, a copy of four-pass-review's, scoped to `*regression-reviewer`.
- `evals/`: two recall cases, a precision case that is a matched pair with one of them, and a nothing-in-history case, each built as a real git history by `evals/repo_builder.py` with deterministic SHAs.
- Tests: the scan, co-change detection and the builder against real repositories, skill invariants, the eval suite's own checks, and a standard-library lint pass.
