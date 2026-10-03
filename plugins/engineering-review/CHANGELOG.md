# Changelog

All notable changes to this plugin are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this plugin adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `review` skill with `--plan`: resolves the working tree, a ref range or a PR, and shows which plugins the change needs, the files that selected each, why each other plugin is skipped, and which follow-ups to offer. Marks selected plugins that are not installed. Launches no agents and writes no files; running the plan is the next version.
- `registry.json`: four-pass-review, migration-safety and change-impact as selectable plugins, test-gap-writer as a follow-up offered after four-pass-review. Each plugin's include and exclude patterns mirror its own early stop.
- `scripts/plan.py`: selection by path patterns, no model, including untracked files. Validates the registry before planning.
- Tests: a 20-row table of change shapes and the plugins each must select (this plugin's eval suite, free and deterministic), glob semantics, registry validation, and the CLI against a real git repository.
- `scripts/check-registry.py` at the repository root, run by `check.sh`: every marketplace plugin has a registry entry, every entry's skill exists, and claimed finding prefixes match the finding contract.
