# Finding contract

The shape of `findings.json`: what a plugin in this repository writes when it reports findings, and what any plugin that reads findings accepts. One definition, so a reviewer plugin and a consumer plugin can change independently without silently breaking each other.

| File | What it is |
|---|---|
| `finding.schema.json` | The contract, as JSON Schema. The source of truth. |
| `finding_contract.py` | A standard-library validator that reads the schema. `python3 finding_contract.py findings.json` exits 0 when valid, 1 with one error per line when not. |
| `tests/` | The validator's tests. Run by `scripts/check.sh`. |

This directory is the canonical copy. Each plugin that writes or reads findings carries an identical copy of the schema and the validator beside the script that uses them, because a plugin may not read outside its own directory. `scripts/sync-shared.py` lists the copies and CI fails when one differs. Edit here, then run `python3 scripts/sync-shared.py --write`.

## A finding

`findings.json` is a JSON list with one object per finding. With no findings it is `[]`.

```json
{
  "id": "COR-1",
  "title": "export_row dereferences invoice.customer when it is optional",
  "severity": "critical",
  "confidence": 92,
  "pass": "correctness",
  "path": "billing/exporter.py",
  "line": 7,
  "end_line": 8,
  "body": "API-created invoices have no customer, so the export raises and the batch aborts.",
  "fix": "Guard the None case and emit an empty email column."
}
```

| Field | Required | Rule |
|---|---|---|
| `id` | yes | Upper-case prefix, hyphen, number: `COR-1`. Unique within the list. The prefix names the pass. |
| `title` | yes | One line, not empty. |
| `severity` | yes | `critical`, `major` or `minor`. |
| `confidence` | yes | Integer, 0 to 100. |
| `pass` | yes | Lower-case, hyphens allowed: `correctness`, `migration-safety`. |
| `path` | yes | Repository-relative. Not absolute, no `..` segment. |
| `line` | yes | Integer from 1. A head-version line, or a base-version line when `side` is `LEFT`. |
| `body` | yes | Why it matters and the key evidence. Not empty. |
| `end_line` | no | Last line of a range, inclusive. Not less than `line`. |
| `side` | no | `LEFT` for a finding about deleted code; omitted means `RIGHT`. |
| `fix` | no | A concrete suggestion in words. |
| `suggestion` | no | Literal replacement text for exactly the anchored lines (a GitHub suggestion block). |

No other fields. An unknown field is an error, so a typo such as `file` for `path` is caught instead of passing as an extra.

## Prefixes and passes in use

| Prefix | `pass` | Plugin |
|---|---|---|
| `CMP-` | `completeness` | four-pass-review |
| `COR-` | `correctness` | four-pass-review |
| `CPL-` | `compliance` | four-pass-review |
| `CNS-` | `consistency` | four-pass-review |
| `MIG-` | `migration-safety` | migration-safety |
| `REG-` | `regression-hunter` | regression-hunter |
| `ADHOC-` | `adhoc` | test-gap-writer, for a request typed in plain words |

The contract does not enumerate passes, so a new plugin adds its own without a contract change. Pick a prefix nobody uses and add a row here.

## Writing and reading

- **A plugin that writes findings** writes this shape to a temporary directory outside the repository and runs the validator on it before telling anyone where it is. The report a person reads is free to change layout; this file is not.
- **A plugin that reads findings** validates them on the way in and refuses an invalid file with the validator's errors. It does not repair input: a guessed severity or line is worse than a refusal.

## Versioning

This is v1. The version is in the schema's `$id`.

- **Compatible (stays v1):** adding an optional field, widening an enum, loosening a pattern. Update the schema here, sync the copies, and every reader accepts the new shape at once.
- **Breaking (v2):** removing or renaming a field, making an optional field required, narrowing a type or enum. Ship `finding.v2.schema.json` beside v1, teach readers to accept both, then move writers over.
