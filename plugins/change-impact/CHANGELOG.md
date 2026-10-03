# Changelog

All notable changes to this plugin are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this plugin adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **The read-only guard (the copy of four-pass-review's) denies git options that run a command.** `git grep -O<cmd>` (`--open-files-in-pager`) and `--upload-pack` on `git fetch` and `git ls-remote` run the command they are given, and `git cat-file --filters` runs configured filters; all were auto-allowed as reads. Denied options are now also matched by prefix, because git accepts any unambiguous abbreviation of a long option: `git grep --textc`, `git fetch --for` and `git grep --open=<cmd>` got past the exact-name checks.

### Added

- `impact-analyst` agent: starts from the scan, drops name collisions, follows callers up to two more hops, and finds what a name search cannot see in a Laravel app (routes, middleware, the event-to-listener map, observers, the scheduler, dispatched jobs, container bindings, policies, views, config keys). Lists the tests that reach the change and the changed symbols none do, the data it touches, and contracts such as event and job payloads already serialized on the queue. Facts only: no severities, no verdict.
- `map` skill: resolves the working tree, a ref range or a PR; runs the scan and stops without launching anything when only docs, tests, lockfiles or assets changed; `--quick` maps from the scan alone with no agent; writes `impact.md` and a validated `impact.json`.
- No launch-time preamble: the skill reads the repository state in Step 1, because a preamble command that fails stops the skill from loading.
- The reply is the rendered map, not a summary of it; the files are saved as well. Measured: told only to write and save the report, the lead summarised it.
- `scripts/impact-scan.py`: finds the declarations a diff touches in PHP, Python, JS/TS, Go and Ruby, whether each was added, modified or removed and whether its signature changed, and every reference to them at the right revision, including untracked files, tagged where the referencing file is an entry point by convention. A constructor change searches for its class.
- `impact.schema.json` and `impact_contract.py`: the impact contract, separate from the finding contract because a map is facts, not findings.
- The read-only guard, a copy of four-pass-review's kept identical by `scripts/sync-shared.py`, scoped to `*impact-analyst`.
- `evals/`: three recall cases and a precision case, each built so the scan alone fails it, and a nothing-to-map case.
- Tests: the scan and the contract (including against a real git repository), skill invariants, the eval suite's own checks, and a standard-library lint pass.
