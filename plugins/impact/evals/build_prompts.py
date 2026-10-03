#!/usr/bin/env python3
"""Regenerate each case's prompt.md from the fixture it maps.

Each fixture is `INTENT.md` and two trees, `base/` and `head/`. The prompt
inlines both, because an eval run's workspace has no repository in it. The
scan in the prompt is produced by the skill's own `impact-scan.py` core, run
over a `-U0` diff of the two trees with an in-memory search standing in for
`git grep`, so the packet the analyst sees is the one the skill would build.

    python3 evals/build_prompts.py           # rewrite prompts
    python3 evals/build_prompts.py --check   # fail if any prompt is stale (CI)
"""

from __future__ import annotations

import difflib
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
SCRIPT = os.path.join(os.path.dirname(HERE), "skills", "map", "scripts", "impact-scan.py")

_spec = importlib.util.spec_from_file_location("impact_scan", SCRIPT)
scan_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan_mod)  # type: ignore[union-attr]

LANG = {".php": "php", ".json": "json", ".md": "markdown"}

# case name -> fixture directory
CASES = {
    "recall-route-job-schedule": "invoice-total",
    "recall-event-listener": "order-event",
    "recall-untested": "untested-export",
    "precision-name-collision": "collision",
    "nothing-to-map": "docs-and-tests",
}

FRONTMATTER = """---
max_turns: 40
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash]
---
"""

PACKET = """## Impact Packet (already resolved -- do not rebuild it)

There is no git repository, no checkout and no files on disk: nothing to clone,
fetch, glob, `ls` or `git` at. Skip Steps 1 and 2 of the skill entirely. The
target is resolved and `impact-scan.py` has already run; its output is below.
Act on it exactly as Step 2 says: if `analyse` is false, stop there. Otherwise
go straight to Step 3, and brief the analyst with the files below in place of
`git` commands. The files at head are the whole repository.

Time spent looking for files is time not spent analysing, and there is nothing
to find.
"""


def strip_annotations(text: str) -> str:
    """Drop `EVAL:` comment lines: they name what the case measures."""
    return "\n".join(ln for ln in text.splitlines() if "EVAL:" not in ln) + "\n"


def tree(root: str) -> dict[str, str]:
    out = {}
    if not os.path.isdir(root):
        return out
    for dirpath, _, names in os.walk(root):
        for n in names:
            path = os.path.join(dirpath, n)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            with open(path, encoding="utf-8") as fh:
                out[rel] = strip_annotations(fh.read())
    return out


def unified(base: dict[str, str], head: dict[str, str]) -> str:
    out = []
    for p in sorted(set(base) | set(head)):
        a, b = base.get(p), head.get(p)
        if a == b:
            continue
        out.extend(difflib.unified_diff(
            (a or "").splitlines(), (b or "").splitlines(),
            fromfile="/dev/null" if a is None else f"a/{p}",
            tofile="/dev/null" if b is None else f"b/{p}", n=0, lineterm=""))
    return "\n".join(out) + "\n"


def memory_search(base: dict[str, str], head: dict[str, str]):
    def search(name: str, rev: str):
        files = base if rev == "base" else head
        rx = re.compile(rf"(?<![\w$]){re.escape(name)}(?![\w$])")
        return [(p, i, line) for p, text in sorted(files.items())
                for i, line in enumerate(text.splitlines(), start=1) if rx.search(line)]
    return search


def block(path: str, text: str, note: str = "") -> str:
    lang = LANG.get(os.path.splitext(path)[1], "")
    return f"### `{path}`{note}\n\n```{lang}\n{text.rstrip()}\n```\n"


def build(case: str) -> str:
    d = os.path.join(FIXTURES, CASES[case])
    base, head = tree(os.path.join(d, "base")), tree(os.path.join(d, "head"))
    with open(os.path.join(d, "INTENT.md"), encoding="utf-8") as fh:
        intent = fh.read().replace("# Change intent\n\n", "").strip()
    diff = unified(base, head)
    result = {"base": "base", "head": "head"}
    result.update(scan_mod.scan(base, head, diff, memory_search(base, head)))

    body = [FRONTMATTER,
            "Map the impact of the change below.\n",
            PACKET,
            "Use the impact skill.\n",
            "## Change intent\n", intent + "\n",
            "## impact-scan.py output\n",
            "```json\n" + json.dumps(result, indent=2) + "\n```\n",
            "## Diff\n",
            "```diff\n" + diff.rstrip() + "\n```\n",
            "## Files at head (the whole repository after this change)\n"]
    body += [block(p, head[p]) for p in sorted(head)]
    removed = sorted(set(base) - set(head))
    if removed:
        body.append("## Files deleted by this change (as at base)\n")
        body += [block(p, base[p]) for p in removed]
    return "\n".join(body)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    check = "--check" in args
    stale = []
    for case in CASES:
        target = os.path.join(HERE, case, "prompt.md")
        want = build(case)
        have = ""
        if os.path.exists(target):
            with open(target, encoding="utf-8") as fh:
                have = fh.read()
        if want == have:
            continue
        if check:
            stale.append(os.path.relpath(target, os.path.dirname(HERE)))
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(want)
        print("wrote", os.path.relpath(target, os.path.dirname(HERE)))
    if stale:
        print("stale prompts (run python3 evals/build_prompts.py):", file=sys.stderr)
        for s in stale:
            print("  " + s, file=sys.stderr)
        return 1
    if check:
        print("all prompts up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
