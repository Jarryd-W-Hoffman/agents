# Changelog

All notable changes to this plugin are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this plugin adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- regression-hunter in the registry: selected for any change to code, config or tests (a loosened regression test is a regression), skipped for docs, assets and lockfiles. The selection table covers it.
- **Running the plan.** Without `--plan`, the skill launches one `general-purpose` subagent per selected, installed plugin, all in one message; each runs that plugin's skill unchanged, so each plugin's own agents run exactly as they do alone. Subagents reply in a fixed block (status, file paths, verdict, reason, note), which the lead records in `results.json`. Each runner saves its plugin's output in its own `mktemp -d` directory, because subagents share the session scratchpad and plugins use the same file names.
- `scripts/merge.py`: validates each plugin's `findings.json` against the finding contract and the registry's prefixes, merges the findings without combining any, flags findings from different plugins on overlapping lines for a person, and computes one verdict. Any selected plugin that did not report, for any reason, makes it `INCOMPLETE`. A note (for example a report.md that could not be saved) never changes a plugin's status: the contract file is the result.
- The merged report, `report.md` and a validated merged `findings.json`; test-gap-writer offered afterwards with that file, never run without asking.
- `review` skill with `--plan`: resolves the working tree, a ref range or a PR, and shows which plugins the change needs, the files that selected each, why each other plugin is skipped, and which follow-ups to offer. Marks selected plugins that are not installed. With `--plan` it launches nothing and writes nothing.
- `registry.json`: four-pass-review, migration-safety and change-impact as selectable plugins, test-gap-writer as a follow-up offered after four-pass-review. Each plugin's include and exclude patterns mirror its own early stop.
- `scripts/plan.py`: selection by path patterns, no model, including untracked files. Validates the registry before planning.
- Tests: a 20-row table of change shapes and the plugins each must select (this plugin's eval suite, free and deterministic), glob semantics, registry validation, and the CLI against a real git repository.
- `scripts/check-registry.py` at the repository root, run by `check.sh`: every marketplace plugin has a registry entry, every entry's skill exists, and claimed finding prefixes match the finding contract.

### Changed

- **Renamed from `engineering-review` to `review`, so commands read as subject and verb: `/engineering-review:review` is now `/review:all`.** The plan is its own skill, `/review:plan`, instead of a `--plan` flag; it has no `Agent` or `Write` in its `allowed-tools`, so it cannot run anything. The registry, scripts and templates moved from `skills/review/` to the plugin root, shared by both skills. Reinstall with `/plugin install review@jarrydh-agents`; agent types are now `review:<agent>`, with the agent names unchanged. Finding ID prefixes are unchanged.

