#!/usr/bin/env python3
"""Validate a findings list against the finding contract (finding.schema.json).

The schema beside this file is the contract. This module reads it and checks
a findings list against it, so there is one definition of a finding and the
code cannot drift from it. It implements only the JSON Schema keywords that
schema uses (type, required, properties, additionalProperties, enum, pattern,
minLength, minimum, maximum, items) plus the two rules a schema cannot express:
ids are unique within a list, and end_line is not less than line.

Canonical copy: shared/finding-contract/ at the repository root. Each plugin
carries an identical copy of this file and the schema, because a plugin may
not read outside its own directory. Edit the canonical pair and run
`python3 scripts/sync-shared.py --write`; CI fails when a copy differs.

Usage:
    finding_contract.py findings.json     exit 0 when valid; 1 with one error
                                          per line on stderr when not
As a module:
    from finding_contract import validate
    errors = validate(findings)           [] when valid

Standard library only; no third-party dependencies.
"""

from __future__ import annotations

import json
import os
import re
import sys

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finding.schema.json")

# JSON has no integer type of its own and Python's bool is an int, so both
# need saying explicitly: true is not a confidence and 92.0 is not a line.
_TYPES = {
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
}

_schema_cache: dict | None = None


def load_schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            _schema_cache = json.load(fh)
    return _schema_cache


def _check(value, schema: dict, where: str, errors: list[str]) -> None:
    expected = schema.get("type")
    if expected and not _TYPES[expected](value):
        errors.append(f"{where}: expected {expected}, got {type(value).__name__}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: {value!r} is not one of {', '.join(schema['enum'])}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{where}: must not be empty")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{where}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, int):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{where}: {value} is below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{where}: {value} is above {schema['maximum']}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{where}: missing required field '{key}'")
        for key, item in value.items():
            if key in props:
                _check(item, props[key], f"{where}.{key}", errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{where}: unknown field '{key}'")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            _check(item, schema["items"], f"{where}[{i}]", errors)


def _label(i: int, finding) -> str:
    fid = finding.get("id") if isinstance(finding, dict) else None
    return f"finding {i}" + (f" ({fid})" if isinstance(fid, str) else "")


def validate(findings) -> list[str]:
    """Every way `findings` breaks the contract, one message each; [] when it holds."""
    errors: list[str] = []
    _check(findings, load_schema(), "findings", errors)
    if not isinstance(findings, list):
        return errors
    seen: dict[str, int] = {}
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if isinstance(fid, str):
            if fid in seen:
                errors.append(f"{_label(i, f)}: id repeats finding {seen[fid]}")
            seen.setdefault(fid, i)
        line, end = f.get("line"), f.get("end_line")
        if isinstance(line, int) and isinstance(end, int) and end < line:
            errors.append(f"{_label(i, f)}: end_line {end} is before line {line}")
    # Name findings by id where there is one: "findings[3].line" is harder to
    # act on than "finding 3 (COR-2).line".
    out = []
    for e in errors:
        m = re.match(r"^findings\[(\d+)\](.*)$", e)
        if m and isinstance(findings[int(m.group(1))], dict):
            i = int(m.group(1))
            e = _label(i, findings[i]) + m.group(2)
        out.append(e)
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0].startswith("-"):
        print("usage: finding_contract.py <findings.json>", file=sys.stderr)
        return 2
    try:
        with open(args[0], encoding="utf-8") as fh:
            findings = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"finding_contract: cannot read {args[0]}: {exc}", file=sys.stderr)
        return 1
    errors = validate(findings)
    for e in errors:
        print(f"finding_contract: {e}", file=sys.stderr)
    if errors:
        return 1
    print(f"finding_contract: {len(findings)} finding(s) valid", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
