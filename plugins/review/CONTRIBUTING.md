# Contributing to review

Repository-wide conventions are in the root [CONTRIBUTING.md](../../CONTRIBUTING.md). Paths here are relative to `plugins/review/`.

## The invariants

1. **The script decides.** Selection is `registry.json` applied to the changed paths by `plan.py`. The lead shows the plan and may add a note after it; it never adds or drops a plugin. Keep judgement out of selection, so the plan stays free, deterministic and exactly testable.
2. **A plugin that does not run is never a clean result.** Not installed, failed, or no usable reply: the merge makes the verdict `INCOMPLETE`.
3. **Follow-ups that write are offered, not run.** testgaps edits files. It stays `kind: follow-up` with an empty `include`.
4. **Every plugin runs as it runs alone.** Each is invoked in its own subagent with the user's target and no flags, and its findings are merged as written. The lead has no `Skill` tool: it never runs a plugin in its own context.
5. **The merge decides the verdict.** `merge.py` applies the rules; the lead renders what it computed. A note never changes a plugin's status, and only a contract-valid `findings.json` or `impact.json` counts as reporting.

## Changing selection

Edit the plugin's `include` or `exclude` in `registry.json`, then add the change shape that motivated it to `CASES` in `tests/test_plan.py`. A pattern change with no new case is a change nobody has checked.

## Before opening a PR

```bash
../../scripts/check.sh review
```

Add an entry under `[Unreleased]` in `CHANGELOG.md`.
