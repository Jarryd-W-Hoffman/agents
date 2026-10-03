#!/usr/bin/env python3
"""Regenerate each case's prompt.md from the fixture it reviews.

Each fixture is a commit history (see repo_builder.py). This builds it into a
real git repository, runs the skill's own history-scan.py on it, and inlines
what the reviewer would read: the scan, `git show` of every commit the scan
lists, the diff, and the changed files at head. An eval run's workspace has
no repository, so the history travels in the prompt; building it for real
means the SHAs, the line overlaps and the revert links in that prompt are
the ones git produces, not ones written by hand.

    python3 evals/build_prompts.py           # rewrite prompts
    python3 evals/build_prompts.py --check   # fail if any prompt is stale (CI)

Needs git.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
sys.path.insert(0, HERE)
import repo_builder  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "history_scan", os.path.join(os.path.dirname(HERE), "skills", "hunt", "scripts", "history-scan.py"))
hs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hs)  # type: ignore[union-attr]

LANG = {".php": "php", ".json": "json", ".md": "markdown"}

# case name -> fixture directory
CASES = {
    "recall-revert-reintroduced": "revert-reintroduced",
    "recall-fix-guard-removed": "fix-guard-removed",
    "precision-fix-guard-kept": "fix-guard-kept",
    "nothing-in-history": "quiet-history",
}

FRONTMATTER = """---
max_turns: 40
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash]
---
"""

PACKET = """## History Packet (already resolved -- do not rebuild it)

There is no git repository, no checkout and no files on disk: nothing to clone,
fetch, glob, `ls` or `git` at. Skip Steps 1 and 2 of the skill entirely. The
target is resolved and `history-scan.py` has already run; its output is below.
Act on it exactly as Step 2 says: if `analyse` is false, stop there. Otherwise
go straight to Step 3, and brief the reviewer with everything below in place
of `git` commands: the `git show` output of every commit the scan lists, the
diff, and the changed files at head.

Time spent looking for files is time not spent reviewing, and there is nothing
to find.
"""


def strip_annotations(text: str) -> str:
    """Drop `EVAL:` comment lines: they name the seeded regression or the bait."""
    out = "\n".join(ln for ln in text.splitlines() if "EVAL:" not in ln)
    return out + ("\n" if text.endswith("\n") else "")


def _git(repo: str, *args: str) -> str:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout


def block(path: str, text: str, note: str = "") -> str:
    lang = LANG.get(os.path.splitext(path)[1], "")
    return f"### `{path}`{note}\n\n```{lang}\n{text.rstrip()}\n```\n"


def build(case: str) -> str:
    fixture = os.path.join(FIXTURES, CASES[case])
    repo = tempfile.mkdtemp()
    try:
        repo_builder.build(fixture, repo, strip=strip_annotations)
        cwd = os.getcwd()
        os.chdir(repo)
        try:
            result = hs.scan("HEAD", None)
        finally:
            os.chdir(cwd)
        result = dict({"base": "HEAD", "head": "working tree"}, **result)
        diff = _git(repo, "diff", "--no-color", "HEAD")
        untracked = _git(repo, "ls-files", "--others", "--exclude-standard").split()
        shas = list(dict.fromkeys(c["sha"] for f in result["files"] for c in f["commits"]))
        shows = [_git(repo, "show", "--no-color", "--format=commit %H%nDate: %ad%n%n%B", "--date=short", s)
                 for s in shas]
        changed = sorted(set(_git(repo, "diff", "--name-only", "HEAD").split()) | set(untracked))
        heads = {}
        for p in changed:
            with open(os.path.join(repo, p), encoding="utf-8") as fh:
                heads[p] = fh.read()
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    with open(os.path.join(fixture, "INTENT.md"), encoding="utf-8") as fh:
        intent = fh.read().replace("# Change intent\n\n", "").strip()
    body = [FRONTMATTER, "Hunt for regressions in the change below.\n", PACKET,
            "Use the regression-hunter skill.\n",
            "## Change intent\n", intent + "\n",
            "## history-scan.py output\n",
            "```json\n" + json.dumps(result, indent=2) + "\n```\n"]
    if shows:
        body.append("## The commits the scan lists (git show)\n")
        body += [f"```diff\n{s.rstrip()}\n```\n" for s in shows]
    body.append("## Diff of the change (tracked files)\n")
    body.append("```diff\n" + (diff.rstrip() or "(none)") + "\n```\n")
    body.append("## Changed files at head\n")
    body += [block(p, heads[p], " (new, untracked)" if p in untracked else "") for p in changed]
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
