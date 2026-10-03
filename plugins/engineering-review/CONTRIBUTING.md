# Contributing to engineering-review

Repository-wide conventions are in the root [CONTRIBUTING.md](../../CONTRIBUTING.md). Paths here are relative to `plugins/engineering-review/`.

## The invariants

1. **The script decides.** Selection is `registry.json` applied to the changed paths by `plan.py`. The lead shows the plan and may add a note after it; it never adds or drops a plugin. Keep judgement out of selection, so the plan stays free, deterministic and exactly testable.
2. **A plugin that does not run is never a clean result.** The plan marks plugins that are not installed; when running is built, they are reported as not run.
3. **Follow-ups that write are offered, not run.** test-gap-writer edits files. It stays `kind: follow-up` with an empty `include`.
4. **This version plans only.** The skill's `allowed-tools` has no `Agent`, `Skill` or `Write`; `tests/test_skill_invariants.py` pins that until the running version replaces it.

## Changing selection

Edit the plugin's `include` or `exclude` in `skills/review/registry.json`, then add the change shape that motivated it to `CASES` in `tests/test_plan.py`. A pattern change with no new case is a change nobody has checked.

## Before opening a PR

```bash
../../scripts/check.sh engineering-review
```

Add an entry under `[Unreleased]` in `CHANGELOG.md`.
