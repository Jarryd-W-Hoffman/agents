# agents

Claude Code plugins, installable from this repository as a local marketplace. Each plugin is a self-contained directory under `plugins/` with its own manifest, agents, skills, hooks, tests and changelog.

| Plugin | What it does | Docs |
|---|---|---|
| `four-pass-review` | Reviews a change in four independent passes (completeness, correctness, compliance, consistency) run in parallel by read-only agents, and merges the results into one ranked report. Can post it to a PR. | [README](plugins/four-pass-review/README.md) · [CHANGELOG](plugins/four-pass-review/CHANGELOG.md) |
| `test-gap-writer` | Turns review findings into tests. One writer agent per finding writes the smallest test that proves it, runs it, and reports whether it reproduced the defect. A hook confines the writer to test files. | [README](plugins/test-gap-writer/README.md) · [CHANGELOG](plugins/test-gap-writer/CHANGELOG.md) |
| `migration-safety` | Reviews database migrations for what breaks in production: the running release against the new schema during a deploy, table locks, data loss, constraints existing rows violate, missing rollbacks. A script finds the migrations first, so a change with none launches nothing. | [README](plugins/migration-safety/README.md) · [CHANGELOG](plugins/migration-safety/CHANGELOG.md) |
| `change-impact` | Maps what a change touches and what reaches it: callers, routes, scheduled tasks, queued jobs, event listeners, the tests that reach it and the changed code none do, data and contracts. Facts, not a review. A script finds references first; one agent verifies them and finds what grep cannot. | [README](plugins/change-impact/README.md) · [CHANGELOG](plugins/change-impact/CHANGELOG.md) |
| `engineering-review` | Works out which of the plugins above a change needs, from the files it touches and with no model, and shows the plan: what would run and why, what is skipped and why, what to offer afterwards. Running the plan is the next step. | [README](plugins/engineering-review/README.md) · [CHANGELOG](plugins/engineering-review/CHANGELOG.md) |

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
  migration-safety/
  change-impact/
  engineering-review/
shared/
  finding-contract/      the findings.json schema every plugin reads and writes,
                         and its validator; canonical copy, see its README
scripts/
  check.sh               every check CI runs, for every plugin or one
  sync-shared.py         checks (or with --write, refreshes) each plugin's copy of shared/
  check-registry.py      checks engineering-review's registry against the marketplace
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
