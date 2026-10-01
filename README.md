# agents

Claude Code plugins, installable from this repository as a local marketplace. Each plugin is a self-contained directory under `plugins/` with its own manifest, agents, skills, hooks, tests and changelog.

| Plugin | What it does | Docs |
|---|---|---|
| `four-pass-review` | Reviews a change in four independent passes (completeness, correctness, compliance, consistency) run in parallel by read-only agents, and merges the results into one ranked report. Can post it to a PR. | [README](plugins/four-pass-review/README.md) · [CHANGELOG](plugins/four-pass-review/CHANGELOG.md) |
| `test-gap-writer` | Turns review findings into tests. One writer agent per finding writes the smallest test that proves it, runs it, and reports whether it reproduced the defect. A hook confines the writer to test files. | [README](plugins/test-gap-writer/README.md) · [CHANGELOG](plugins/test-gap-writer/CHANGELOG.md) |

## Installation

Add the repository as a marketplace once, then install whichever plugins you want:

```text
/plugin marketplace add /path/to/agents
/plugin install four-pass-review@jarrydh-agents
/plugin install test-gap-writer@jarrydh-agents
```

To try a plugin for one session without installing it:

```bash
claude --plugin-dir /path/to/agents/plugins/four-pass-review
```

Each plugin's README covers its usage and how to copy its pieces into a project without the plugin system.

## Layout

```text
.claude-plugin/
  marketplace.json       lists every plugin under plugins/
plugins/
  four-pass-review/      one directory per plugin; see its README
  test-gap-writer/
scripts/
  check.sh               every check CI runs, for every plugin or one
SECURITY.md              reporting process and the threat model of the guards
CONTRIBUTING.md          repository-wide conventions; each plugin has its own
.github/                 CI, dependabot, issue and PR templates
```

## Development

```bash
./scripts/check.sh                       # everything CI runs, every plugin
./scripts/check.sh four-pass-review      # one plugin
./scripts/check.sh --tests               # just the Python suites
./scripts/check.sh --manifests           # just manifest/component validation
```

The Python in this repository is standard library only and supports 3.9 and up, because hooks run under whatever `python3` the user has and stock macOS is still on 3.9. CI runs the suites on 3.9 and 3.13.

## Licence

MIT, see [LICENSE](LICENSE).
