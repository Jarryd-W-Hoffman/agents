# impact

A Claude Code plugin that maps what a change touches and what reaches it: the callers, HTTP routes, console commands, scheduled tasks, queued jobs and event listeners that lead to the changed code; the tests that exercise it and the changed code no test reaches; the data and config it touches; and the contracts other systems depend on.

It is a map, not a review. There are no severities and no verdict, and nothing in it says the change is wrong. Use it before reviewing, before writing tests, or before deploying, to know where to look.

| Piece | What it does |
|---|---|
| `map` skill | Resolves the target, runs the scan, briefs one analyst, writes `impact.md` and `impact.json`. |
| `impact-analyst` agent | Starts from the scan, drops name collisions, follows callers up to two more hops, and finds what a name search cannot: routes, the scheduler, event wiring, container bindings, policies. Read-only, enforced by a hook. |
| `impact-scan.py` | No model. Finds the declarations the diff touches (PHP, Python, JS/TS, Go, Ruby), whether each was added, modified or removed and whether its signature changed, and every reference to them by name, tagged where the referencing file is an entry point by convention. |

## Cost

- **Nothing to map, nothing launched.** A change to docs, tests, lockfiles or assets alone stops after the scan.
- **`--quick`**: the scan alone, turned into a map. No agent. Names matched, collisions kept, nothing wired by configuration found; the map says so on every line.
- **Default**: one analyst agent.

## Installation

```bash
claude --plugin-dir /path/to/agents/plugins/impact      # one session
```

```text
/plugin marketplace add /path/to/agents
/plugin install impact@jarrydh-agents
```

Or copy the pieces into a project, from this plugin's directory:

```bash
cd plugins/impact
cp agents/impact-analyst.md your-project/.claude/agents/
cp -r skills/map            your-project/.claude/skills/impact-map
cp -r hooks                 your-project/.claude/impact-hooks/
```

Copying does not bring the read-only guard with it; wire it as in [fourpass's README](../fourpass/README.md#external-tooling-strictly-read-only), with `READONLY_GUARD_AGENTS='*impact-analyst'`.

## Usage

```text
/impact:map                    # working tree against HEAD, including untracked files
/impact:map 318                # pull request #318
/impact:map main...feature/x   # a ref range
/impact:map --quick            # the scan alone, no agent
```

```text
Use the impact-analyst agent: what reaches InvoiceService::total?
```

## Output

```markdown
# Change impact: PR #318: Discounts on invoices

**Mode:** full — verified by the impact-analyst
**Changed:** 1 symbols in 1 files (4e1c2a9 → 9b7f310)
**Reach:** Every invoice total shown over HTTP and in the daily reminder emails.

## Entry points

| Kind | Name | Where | Reaches |
|---|---|---|---|
| http | GET /invoices/{invoice} | `routes/web.php:6` | `InvoiceService::total` |
| schedule | invoices:remind, daily 08:00 | `routes/console.php:5` | `InvoiceService::total` |
| queue | SendInvoiceReminder | `app/Jobs/SendInvoiceReminder.php:17` | `InvoiceService::total` |

## Tests

- **Covering:** `tests/Unit/InvoiceServiceTest.php` → `InvoiceService::total`

## Risks

- **Reminder emails** — the daily schedule reaches total() through a command and a queued job, and no test covers that path (`routes/console.php:5`, `app/Jobs/SendInvoiceReminder.php:20`)
```

Every run that maps something saves `impact.md` and `impact.json` to a temporary directory outside the repository. `impact.json` follows `skills/map/scripts/impact.schema.json` and is validated before the skill mentions it.

`impact.json` is a separate contract from the repository's [finding contract](../../shared/finding-contract/README.md), on purpose: findings are opinions with a severity, and this is a list of facts. No other plugin reads it yet. The plan is for reviewers to take it as optional context later, once its usefulness has been measured.

## Limits

- The scan finds declarations line by line and attributes a changed line to the nearest declaration above it, so a change between two methods can land on the first. The analyst reads the diff and corrects it.
- References are matched by name and capped at 40 per symbol. The map says when a cap was hit.
- It reads code. Dynamic dispatch the code does not spell out (a class name built from a string at runtime) can be missed; the analyst lists what it could not resolve under Limits.
- It does not judge correctness and does not post anywhere.

## Layout

```text
.claude-plugin/plugin.json
agents/impact-analyst.md        the analyst
skills/map/
  SKILL.md                      the lead
  references/
    analyst-brief.md            the brief sent to the analyst
    report-template.md          impact.md's format
  scripts/
    impact-scan.py              the scan, no model
    impact.schema.json          the impact contract
    impact_contract.py          its validator
hooks/
  hooks.json                    registers the read-only guard for the analyst
  readonly-guard.py, guard/     a copy of fourpass's guard
evals/                          claude plugin eval suite; see evals/README.md
tests/
  test_impact_scan.py           the scan and the contract, including against a real git repository
  test_skill_invariants.py      read-only grants, guard scope, the early stop, facts not findings
  test_evals.py                 the eval suite's own checks
  test_lint.py                  standard-library lint
```

## Development

```bash
../../scripts/check.sh impact
python3 evals/build_prompts.py        # after editing fixtures
```
