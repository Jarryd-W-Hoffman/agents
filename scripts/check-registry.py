#!/usr/bin/env python3
"""Check engineering-review's registry against the plugins that actually exist.

The registry lives inside the engineering-review plugin, and a plugin's own
tests may not read outside it, so the cross-plugin checks live here and
`scripts/check.sh` runs them:

- every plugin in the marketplace has a registry entry, except
  engineering-review itself, so a new plugin cannot be silently left out of
  every plan;
- every registry entry names a plugin in the marketplace, and its skill
  (`<plugin>:<skill>`) exists as `plugins/<plugin>/skills/<skill>/SKILL.md`;
- the finding prefixes each entry claims are the ones the finding contract's
  README lists for that plugin.

    python3 scripts/check-registry.py

Standard library only; runs on Python 3.9.
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF = "engineering-review"
REGISTRY = os.path.join(ROOT, "plugins", SELF, "skills", "review", "registry.json")
MARKETPLACE = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
CONTRACT_README = os.path.join(ROOT, "shared", "finding-contract", "README.md")


def contract_prefixes() -> dict[str, set[str]]:
    """Plugin -> prefixes, from the 'Prefixes and passes in use' table."""
    out: dict[str, set[str]] = {}
    with open(CONTRACT_README, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^\|\s*`([A-Z]+)-`\s*\|[^|]*\|\s*([^|]+?)\s*\|", line)
            if m:
                for plugin in re.findall(r"[a-z][a-z0-9-]+", m.group(2).split(",")[0]):
                    out.setdefault(plugin, set()).add(m.group(1))
                    break
    return out


def problems() -> list[str]:
    with open(REGISTRY, encoding="utf-8") as fh:
        registry = json.load(fh)
    with open(MARKETPLACE, encoding="utf-8") as fh:
        marketplace = {p["name"] for p in json.load(fh)["plugins"]}
    entries = {p["name"]: p for p in registry["plugins"]}
    out = []
    for name in sorted(marketplace - set(entries) - {SELF}):
        out.append(f"marketplace plugin '{name}' has no entry in {os.path.relpath(REGISTRY, ROOT)}")
    for name, p in sorted(entries.items()):
        if name not in marketplace:
            out.append(f"registry entry '{name}' is not a plugin in the marketplace")
            continue
        _, _, skill = p["skill"].partition(":")
        if not os.path.isfile(os.path.join(ROOT, "plugins", name, "skills", skill, "SKILL.md")):
            out.append(f"registry entry '{name}': skill '{p['skill']}' does not exist")
    table = contract_prefixes()
    for name, p in sorted(entries.items()):
        if p.get("output") != "findings":
            continue
        claimed, listed = set(p["prefixes"]), table.get(name, set())
        if claimed != listed:
            out.append(f"registry entry '{name}' claims prefixes {sorted(claimed)}, "
                       f"the finding contract lists {sorted(listed)}")
    return out


def main() -> int:
    found = problems()
    for p in found:
        print(f"check-registry: {p}", file=sys.stderr)
    if found:
        return 1
    print("check-registry: registry matches the marketplace")
    return 0


if __name__ == "__main__":
    sys.exit(main())
