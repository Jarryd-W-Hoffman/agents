#!/usr/bin/env python3
"""Regenerate each case's prompt.md from the fixture it checks.

Each fixture is two trees: `base/`, what production runs now, and `head/`, the
change. The prompt inlines both, because every eval run gets its own isolated
workspace with no repository in it (see four-pass-review's evals/README.md for
how that was measured). The migration list in the prompt is produced by the
skill's own `find-migrations.py` logic run over the two trees, so the packet
the reviewer sees is the one the skill would have built.

    python3 evals/build_prompts.py           # rewrite prompts
    python3 evals/build_prompts.py --check   # fail if any prompt is stale (CI)
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
SCRIPT = os.path.join(os.path.dirname(HERE), "skills", "check", "scripts", "find-migrations.py")

_spec = importlib.util.spec_from_file_location("find_migrations", SCRIPT)
fm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fm)  # type: ignore[union-attr]

LANG = {".php": "php", ".json": "json", ".md": "markdown"}

# case name -> fixture directory
CASES = {
    "recall-dropped-column": "dropped-column",
    "recall-not-null-no-default": "not-null-no-default",
    "recall-change-drops-nullable": "change-drops-nullable",
    "recall-edited-migration": "edited-migration",
    "precision-expand-contract": "expand-contract",
    "precision-new-table": "new-table",
    "no-migrations": "no-migrations",
}

FRONTMATTER = """---
max_turns: 40
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash]
---
"""

PACKET = """## Migration Packet (already resolved -- do not rebuild it)

There is no git repository, no checkout and no files on disk: nothing to clone,
fetch, glob, `ls` or `git` at. Skip Steps 1 and 2 of the skill entirely. The
target is resolved and `find-migrations.py` has already run; its output is
below. Act on it exactly as Step 2 says: if it lists no migrations, stop there.
Otherwise go straight to Step 3, and brief the reviewer with the files below in
place of `git` commands. Base is the revision production runs now; head is
this change.

Time spent looking for files is time not spent reviewing, and there is nothing
to find.
"""


def strip_annotations(text: str) -> str:
    """Drop `EVAL:` comment lines: they name the seeded defect or the bait."""
    return "\n".join(ln for ln in text.splitlines() if "EVAL:" not in ln)


def tree(root: str) -> dict[str, str]:
    out = {}
    for dirpath, _, names in os.walk(root):
        for n in names:
            path = os.path.join(dirpath, n)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            with open(path, encoding="utf-8") as fh:
                out[rel] = strip_annotations(fh.read())
    return out


def changes(base: dict[str, str], head: dict[str, str]) -> list[tuple[str, str]]:
    """(status letter, path) for every file that differs, as `git diff --name-status` would say."""
    out = []
    for p in sorted(set(base) | set(head)):
        if p not in base:
            out.append(("A", p))
        elif p not in head:
            out.append(("D", p))
        elif base[p] != head[p]:
            out.append(("M", p))
    return out


def block(path: str, text: str, note: str = "") -> str:
    lang = LANG.get(os.path.splitext(path)[1], "")
    return f"### `{path}`{note}\n\n```{lang}\n{text.rstrip()}\n```\n"


def build(case: str) -> str:
    d = os.path.join(FIXTURES, CASES[case])
    base, head = tree(os.path.join(d, "base")), tree(os.path.join(d, "head"))
    with open(os.path.join(d, "INTENT.md"), encoding="utf-8") as fh:
        intent = fh.read().replace("# Change intent\n\n", "").strip()
    diff = changes(base, head)
    found = {"base": "base", "head": "head"}
    found.update(fm.classify("".join(f"{s}\t{p}\n" for s, p in diff), sorted(base)))

    words = {"A": "added", "M": "modified", "D": "deleted"}
    body = [FRONTMATTER,
            "Run a migration safety check of the change below.\n",
            PACKET,
            "Use the migration-safety skill.\n",
            "## Change intent\n", intent + "\n",
            "## find-migrations.py output\n",
            "```json\n" + json.dumps(found, indent=2) + "\n```\n",
            "## Changed files\n",
            "\n".join(f"- {words[s]} `{p}`" for s, p in diff) + "\n",
            "## Files at base (what production runs now)\n"]
    body += [block(p, base[p]) for p in sorted(base)]
    body.append("## Files at head (this change; unchanged files are as at base)\n")
    body += [block(p, head[p], f" ({words[s]})") for s, p in diff if s != "D"]
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
