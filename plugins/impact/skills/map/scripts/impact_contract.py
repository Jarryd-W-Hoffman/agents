#!/usr/bin/env python3
"""Validate an impact map against the impact contract (impact.schema.json).

The schema beside this file is the contract; this reads it, so the two cannot
drift. It implements the JSON Schema keywords that schema uses (type,
required, properties, additionalProperties, enum, pattern, minLength,
minimum, maximum, items, $ref into $defs) plus one rule a schema cannot
express: every risk cites at least one piece of evidence, because a risk
with none is an opinion and this map carries facts.

Usage:
    impact_contract.py impact.json      exit 0 when valid; 1 with one error
                                        per line on stderr when not
As a module:
    from impact_contract import validate
    errors = validate(impact)           [] when valid

Standard library only; no third-party dependencies.
"""

from __future__ import annotations

import json
import os
import re
import sys

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "impact.schema.json")

_TYPES = {
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}

_schema_cache: dict | None = None


def load_schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            _schema_cache = json.load(fh)
    return _schema_cache


def _resolve(schema: dict) -> dict:
    ref = schema.get("$ref")
    if not ref:
        return schema
    if not ref.startswith("#/$defs/"):
        raise ValueError(f"unsupported $ref {ref}")
    return load_schema()["$defs"][ref[len("#/$defs/"):]]


def _check(value, schema: dict, where: str, errors: list[str]) -> None:
    schema = _resolve(schema)
    expected = schema.get("type")
    if expected and not _TYPES[expected](value):
        errors.append(f"{where}: expected {expected}, got {type(value).__name__}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: {value!r} is not one of {', '.join(map(str, schema['enum']))}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{where}: must not be empty")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{where}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, int) and not isinstance(value, bool):
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


def validate(impact) -> list[str]:
    """Every way `impact` breaks the contract, one message each; [] when it holds."""
    errors: list[str] = []
    _check(impact, load_schema(), "impact", errors)
    if isinstance(impact, dict) and isinstance(impact.get("risks"), list):
        for i, r in enumerate(impact["risks"]):
            if isinstance(r, dict) and isinstance(r.get("evidence"), list) and not r["evidence"]:
                errors.append(f"impact.risks[{i}].evidence: a risk must cite at least one path:line")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0].startswith("-"):
        print("usage: impact_contract.py <impact.json>", file=sys.stderr)
        return 2
    try:
        with open(args[0], encoding="utf-8") as fh:
            impact = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"impact_contract: cannot read {args[0]}: {exc}", file=sys.stderr)
        return 1
    errors = validate(impact)
    for e in errors:
        print(f"impact_contract: {e}", file=sys.stderr)
    if errors:
        return 1
    print("impact_contract: impact map valid", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
