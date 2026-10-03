# Contributing to impact

Repository-wide conventions are in the root [CONTRIBUTING.md](../../CONTRIBUTING.md). Everything here is specific to this plugin; paths are relative to `plugins/impact/`.

## The three invariants

1. **Read-only.** The analyst never edits a file or runs the application, its tests or a database client. Keep `disallowedTools` on the agent and the guard in `hooks/hooks.json`.
2. **Nothing to map, no agent.** The skill runs the scan first and stops when `analyse` is false; `--quick` never launches an agent. `tests/test_skill_invariants.py` pins both.
3. **Facts, not findings.** No severity, confidence or verdict anywhere in the agent, the template or `impact.json`. If it starts judging the change, it has become a fifth reviewer, and fourpass already exists.

## The impact contract

`skills/map/scripts/impact.schema.json` is the contract and `impact_contract.py` reads it. Adding an optional field or widening an enum is v1; anything else is v2. When you change it, update the agent's JSON example in `agents/impact-analyst.md` in the same commit; `test_json_example_names_exactly_the_contract_fields` fails if they disagree.

## Shared files

Everything under `hooks/` except `hooks.json` is a copy of fourpass's guard. Edit `plugins/fourpass/hooks/` and run `python3 ../../scripts/sync-shared.py --write`.

## Teaching the scan

- **A language:** add its patterns to `impact-scan.py` (a `class` and a `func` regex, and an entry in `language()`), and a case to `Declarations` in `tests/test_impact_scan.py`.
- **An entry-point convention:** add a `(kind, pattern)` to `ENTRY_RULES`, or to `SELF_ENTRY_RULES` for files that are entry points themselves, with a test.
- Keep the scan cheap and dumb. Anything that needs judgement belongs in the agent's procedure.

## Evals

Every new case must be one the scan alone fails, and `tests/test_evals.py` should say how. Add a fixture under `evals/fixtures/<name>/` (`INTENT.md`, `base/`, `head/`), a line in `CASES` in `evals/build_prompts.py`, and `evals/<case>/graders/criteria.md`, then run `python3 evals/build_prompts.py`.

## Before opening a PR

```bash
../../scripts/check.sh impact
claude --plugin-dir . -p "List the agent types and skills provided by the impact plugin." --max-turns 1
```

Add an entry under `[Unreleased]` in `CHANGELOG.md`.
