# regression-hunter

A Claude Code plugin that checks whether a change undoes what the repository's history already learned:

- a guard, check or lock an earlier **fix** added is removed or bypassed;
- code an earlier commit **reverted** is re-introduced, while the reason for the revert still holds;
- a **regression test** a fix added is deleted or loosened;
- a file that has changed together with this one in every earlier change, its **usual partner**, is left behind.

Every finding names the earlier commit it rests on. A defect no earlier commit speaks to belongs to a correctness review, not here.

| Piece | What it does |
|---|---|
| `hunt` skill | Resolves the target, runs the history scan, briefs one reviewer, writes the report and `findings.json`. |
| `regression-reviewer` agent | Reads each fix and revert the scan found with `git show`, states the invariant it established, and checks the change against it. Read-only, enforced by a hook. |
| `history-scan.py` | No model. Per changed file, at the base: the commits that last touched the changed lines (`git log -L`), the fixes and reverts among them and the issue references they carry, what each revert reverted, and usual partner files missing from the change. |

## Cost

A change whose lines no fix or revert ever touched, on files no revert touched, with no usual partner missing, has no history to regress: the scan says so and **no agent is launched**. Otherwise, one reviewer agent.

## Installation

```bash
claude --plugin-dir /path/to/agents/plugins/regression-hunter
```

```text
/plugin marketplace add /path/to/agents
/plugin install regression-hunter@jarrydh-agents
```

To copy the pieces into a project, follow migration-safety's README, with `READONLY_GUARD_AGENTS='*regression-reviewer'` for the guard.

## Usage

```text
/regression-hunter:hunt                    # working tree against HEAD
/regression-hunter:hunt 412                # pull request #412
/regression-hunter:hunt main...feature/x
/regression-hunter:hunt 412 --threshold 70
```

engineering-review runs it automatically on any change to code, config or tests.

## Output

```markdown
# Regression hunt: working tree

**Verdict:** FAIL
**History:** 1 fix or revert commit(s) on the changed lines, 0 revert(s) on the changed files, 0 usual partner file(s) missing · HEAD → working tree
**Read:** 018c50a
**Threshold:** 80

## Critical (1)

### [REG-1] Retried Stripe webhooks are recorded twice again
`app/Services/PaymentRecorder.php:11` · confidence 93 · regression-hunter
`018c50a` "Fix double charge when Stripe retries a webhook (#311)" made a recorded event never record again; the refactor moved recording into PaymentRecorder without the check, so a retry creates a second Payment and a second receipt.
**Fix:** Keep the provider_event_id check at the top of PaymentRecorder::record.
```

`findings.json` follows the repository's [finding contract](../../shared/finding-contract/README.md) with `REG-` IDs and `pass` set to `regression-hunter`.

## What history counts

- **A fix** is a commit whose message says so: fix, bug, hotfix, regression, patch, crash, incident, outage, security, CVE. Messages lie both ways, so the reviewer reads the diff before relying on one.
- **A revert** is a commit whose subject starts with "Revert" or whose body says "This reverts commit …".
- **A usual partner** is a file that appeared in at least 3 of the changed file's commits and in at least 60% of them, over the last 1,000 commits.
- History is read **at the base**: what the change could undo was committed before it. A new file has none.

Limits: up to 12 changed hunks per file are traced with `git log -L`, and up to 15 commits per file are passed on, most telling first. A shallow clone has shallow history; the scan sees only what git has.

## Layout

```text
agents/regression-reviewer.md
skills/hunt/
  SKILL.md
  references/reviewer-brief.md, report-template.md
  scripts/history-scan.py       the scan, no model
  scripts/finding.schema.json   the finding contract; with finding_contract.py, copies of shared/finding-contract/
hooks/                          the read-only guard, a copy of four-pass-review's
evals/
  repo_builder.py               builds a fixture's history as a real git repository
  build_prompts.py              runs the real scan on it and writes each case's prompt
  fixtures/                     commit histories
tests/
  test_history_scan.py          the scan and the builder, against real repositories
  test_skill_invariants.py      read-only, early stop, every finding tied to a commit
  test_evals.py                 the eval suite's own checks
  test_lint.py
```

## Development

```bash
../../scripts/check.sh regression-hunter
python3 evals/build_prompts.py      # after editing a fixture; needs git
```
