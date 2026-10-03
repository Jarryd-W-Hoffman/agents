# agents

Claude Code plugins, installable from this repository as a local marketplace. Each plugin is a self-contained directory under `plugins/` with its own manifest, agents, skills, hooks, tests and changelog.

| Plugin | Command | What it does | Docs |
|---|---|---|---|
| `fourpass` | `/fourpass:review` | Reviews a change in four independent passes (completeness, correctness, compliance, consistency) run in parallel by read-only agents, and merges them into one ranked report. Can post it to a PR. | [README](plugins/fourpass/README.md) · [CHANGELOG](plugins/fourpass/CHANGELOG.md) |
| `migrations` | `/migrations:check` | Reviews database migrations for what breaks in production: the running release against the new schema during a deploy, table locks, data loss, constraints existing rows violate, missing rollbacks. Launches nothing when a change has no migrations. | [README](plugins/migrations/README.md) · [CHANGELOG](plugins/migrations/CHANGELOG.md) |
| `regressions` | `/regressions:hunt` | Checks whether a change undoes what the history already learned: a fix's guard removed, reverted code re-introduced, a regression test loosened, a usual partner file left behind. Launches nothing when the history has nothing to say. | [README](plugins/regressions/README.md) · [CHANGELOG](plugins/regressions/CHANGELOG.md) |
| `impact` | `/impact:map` | Maps what a change touches and what reaches it: callers, routes, scheduled tasks, queued jobs, event listeners, tests, data and contracts. Facts, not a review. | [README](plugins/impact/README.md) · [CHANGELOG](plugins/impact/CHANGELOG.md) |
| `testgaps` | `/testgaps:write` | Turns review findings into tests. One writer agent per finding writes the smallest test that proves it, runs it, and reports whether it reproduced the defect. A hook confines the writer to test files. | [README](plugins/testgaps/README.md) · [CHANGELOG](plugins/testgaps/CHANGELOG.md) |
| `review` | `/review:plan`, `/review:all` | Works out which of the plugins above a change needs, from the files it touches and with no model. `plan` shows that plan for free; `all` runs the selected plugins in parallel and merges their results into one report and one verdict. | [README](plugins/review/README.md) · [CHANGELOG](plugins/review/CHANGELOG.md) |

## Installation

Add the repository as a marketplace once, then install whichever plugins you want:

```text
/plugin marketplace add /path/to/agents
/plugin install fourpass@jarrydh-agents
/plugin install migrations@jarrydh-agents
/plugin install regressions@jarrydh-agents
/plugin install impact@jarrydh-agents
/plugin install testgaps@jarrydh-agents
/plugin install review@jarrydh-agents
```

To try a plugin for one session without installing it:

```bash
claude --plugin-dir /path/to/agents/plugins/fourpass
```

Each plugin's README covers its usage and how to copy its pieces into a project without the plugin system.

## Layout

```text
.claude-plugin/
  marketplace.json       lists every plugin under plugins/
plugins/
  fourpass/      one directory per plugin; see its README
  testgaps/
  migrations/
  impact/
  review/
  regressions/
shared/
  finding-contract/      the findings.json schema every plugin reads and writes,
                         and its validator; canonical copy, see its README
scripts/
  check.sh               every check CI runs, for every plugin or one
  sync-shared.py         checks (or with --write, refreshes) each plugin's copy of shared/
  check-registry.py      checks the review plugin's registry against the marketplace
SECURITY.md              reporting process and the threat model of the guards
CONTRIBUTING.md          repository-wide conventions; each plugin has its own
.github/                 CI, dependabot, issue and PR templates
```

## Development

```bash
./scripts/check.sh                       # everything CI runs, every plugin
./scripts/check.sh fourpass      # one plugin
./scripts/check.sh --tests               # just the Python suites
./scripts/check.sh --manifests           # just manifest/component validation
```

The Python in this repository is standard library only and supports 3.9 and up, because hooks run under whatever `python3` the user has and stock macOS is still on 3.9. CI runs the suites on 3.9 and 3.13.

## Licence

MIT, see [LICENSE](LICENSE).
