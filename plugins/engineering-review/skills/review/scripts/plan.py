#!/usr/bin/env python3
"""Decide which plugins a change needs, without a model.

Reads the changed files and registry.json, and prints a plan: the plugins
that would run and the files that selected each, the plugins skipped and
why, and the follow-ups to offer afterwards. Nothing is run. Selection is
path patterns only, so it is free, deterministic, and testable as a table of
change shapes, and the plan is the same every time for the same change.

    plan.py --base <rev>                  base against the working tree,
                                          including untracked files
    plan.py --base <rev> --head <rev>     base against a commit
    plan.py --files a.php b.md ...        offline: these paths, no git

A plugin is selected when at least one changed file matches one of its
`include` patterns and none of its `exclude` patterns. A follow-up (kind
"follow-up") is never selected; it is offered when a plugin named in its
`after` list is selected.

Standard library only; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

REGISTRY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "registry.json")
KINDS = ("review", "map", "follow-up")
EVIDENCE_CAP = 5

_glob_cache: dict[str, re.Pattern] = {}


def glob_regex(pattern: str) -> re.Pattern:
    """A glob as a regex over a repository-relative path.

    `*` matches within one segment, `**` matches any number of segments
    (including none), `?` one character. A pattern without a slash matches
    the file name in any directory, so `*.md` means every Markdown file.
    """
    key = pattern
    if key in _glob_cache:
        return _glob_cache[key]
    if pattern == "**":
        rx = re.compile(r"^.*$")
    else:
        if "/" not in pattern:
            pattern = "**/" + pattern
        out, i = "", 0
        while i < len(pattern):
            if pattern.startswith("**/", i):
                out += r"(?:.*/)?"
                i += 3
            elif pattern.startswith("/**", i) and i + 3 == len(pattern):
                out += r"(?:/.*)?"
                i += 3
            elif pattern.startswith("**", i):
                out += r".*"
                i += 2
            elif pattern[i] == "*":
                out += r"[^/]*"
                i += 1
            elif pattern[i] == "?":
                out += r"[^/]"
                i += 1
            else:
                out += re.escape(pattern[i])
                i += 1
        rx = re.compile("^" + out + "$")
    _glob_cache[key] = rx
    return rx


def matches(path: str, patterns: list[str]) -> bool:
    return any(glob_regex(p).match(path) for p in patterns)


def load_registry(path: str = REGISTRY) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def plan(files: list[str], registry: dict) -> dict:
    """The plan for a set of changed paths. Pure: no git, no I/O."""
    files = sorted(set(f for f in files if f))
    selected, skipped, follow_ups = [], [], []
    by_name = {p["name"]: p for p in registry["plugins"]}

    for p in registry["plugins"]:
        if p["kind"] == "follow-up":
            continue
        hits = [f for f in files if matches(f, p["include"]) and not matches(f, p["exclude"])]
        entry = {"plugin": p["name"], "skill": p["skill"], "kind": p["kind"],
                 "output": p["output"], "cost": p["cost"]}
        if hits:
            entry["matched"] = len(hits)
            entry["evidence"] = hits[:EVIDENCE_CAP]
            selected.append(entry)
        else:
            if not files:
                why = "no changed files"
            elif not any(matches(f, p["include"]) for f in files):
                why = "no changed file is the kind it reviews"
            else:
                why = "every matching file is excluded (" + ", ".join(
                    sorted({_first_exclude(f, p["exclude"]) for f in files
                            if matches(f, p["include"])})[:3]) + ")"
            entry["reason"] = why
            skipped.append(entry)

    chosen = {s["plugin"] for s in selected}
    for p in registry["plugins"]:
        if p["kind"] != "follow-up":
            continue
        after = [a for a in p.get("after", []) if a in chosen]
        if after:
            follow_ups.append({"plugin": p["name"], "skill": p["skill"], "after": after,
                               "summary": p["summary"]})

    unknown = [a for p in registry["plugins"] for a in p.get("after", []) if a not in by_name]
    if unknown:
        raise ValueError(f"registry: 'after' names unknown plugins: {', '.join(unknown)}")
    return {"files": files, "selected": selected, "skipped": skipped, "follow_ups": follow_ups}


def _first_exclude(path: str, patterns: list[str]) -> str:
    return next((p for p in patterns if glob_regex(p).match(path)), "?")


def validate_registry(registry: dict) -> list[str]:
    """Structural problems in the registry, one message each; [] when sound."""
    errors = []
    if registry.get("version") != 1:
        errors.append("version must be 1")
    names = set()
    for i, p in enumerate(registry.get("plugins", [])):
        where = f"plugins[{i}]"
        for key in ("name", "skill", "kind", "output", "prefixes", "cost", "summary", "include", "exclude"):
            if key not in p:
                errors.append(f"{where}: missing '{key}'")
        name = p.get("name", "")
        if name in names:
            errors.append(f"{where}: duplicate plugin '{name}'")
        names.add(name)
        if p.get("kind") not in KINDS:
            errors.append(f"{where}: kind must be one of {', '.join(KINDS)}")
        if not str(p.get("skill", "")).startswith(name + ":"):
            errors.append(f"{where}: skill must be namespaced '{name}:<skill>'")
        if p.get("kind") == "follow-up":
            if p.get("include"):
                errors.append(f"{where}: a follow-up is offered, never selected; include must be empty")
            if not p.get("after"):
                errors.append(f"{where}: a follow-up needs 'after'")
        elif not p.get("include"):
            errors.append(f"{where}: include is empty, so it can never be selected")
        for prefix in p.get("prefixes", []):
            if not re.fullmatch(r"[A-Z]+", prefix):
                errors.append(f"{where}: prefix '{prefix}' must be upper-case letters")
    for p in registry.get("plugins", []):
        for a in p.get("after", []):
            if a not in names:
                errors.append(f"{p.get('name')}: 'after' names unknown plugin '{a}'")
    prefixes = [x for p in registry.get("plugins", []) for x in p.get("prefixes", [])]
    for x in sorted({x for x in prefixes if prefixes.count(x) > 1}):
        errors.append(f"prefix '{x}' is claimed by more than one plugin")
    return errors


def git(*args: str) -> str:
    try:
        res = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"cannot run git: {exc}") from exc
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def changed_files(base: str, head: str | None) -> list[str]:
    out = git("diff", "--name-only", "-M", base, *([head] if head else []))
    files = out.splitlines()
    if not head:
        # A file just created and not yet added is part of the change.
        files += git("ls-files", "--others", "--exclude-standard").splitlines()
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", help="the revision the change is taken against")
    ap.add_argument("--head", help="the head revision; omit for the working tree")
    ap.add_argument("--files", nargs="*", help="offline: plan for these paths instead of a git diff")
    ap.add_argument("--registry", default=REGISTRY, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    try:
        registry = load_registry(args.registry)
        errors = validate_registry(registry)
        if errors:
            raise ValueError("registry.json: " + "; ".join(errors))
        if args.files is not None:
            files = args.files
        elif args.base:
            files = changed_files(args.base, args.head)
        else:
            ap.error("give --base, or --files")
            return 2
        result = plan(files, registry)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"plan: {exc}", file=sys.stderr)
        return 1

    out = {"base": args.base, "head": args.head or ("working tree" if args.base else None)}
    out.update(result)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
