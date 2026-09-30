#!/usr/bin/env python3
"""Regenerate each case's prompt.md from the fixtures it reviews.

Why the fixture content is inlined rather than read off disk: every eval run
gets its own isolated workspace, so a prompt that points at
`evals/fixtures/<name>/` sends the agent looking for files that are not there.
Copying them in would need a scaffold script, which is off by default and runs
author-supplied bash as you. Inlining sidesteps both, and keeps each case
runnable with nothing but the plugin.

`evals/fixtures/` stays the source of truth so the fixtures are readable and
editable as ordinary code; this script is what keeps the prompts in step.

    python3 evals/build_prompts.py           # rewrite prompts
    python3 evals/build_prompts.py --check   # fail if any prompt is stale (CI)
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")

LANG = {".py": "python", ".md": "markdown"}

# case name -> (fixture directory, extra instruction paragraph or "")
CASES = {
    "recall-correctness": ("billing", ""),
    "recall-completeness": ("orders", ""),
    "recall-compliance": (
        "payments",
        "Treat `CLAUDE.fixture.md` as the CLAUDE.md governing this module. It is "
        "named with a suffix only so it is not picked up as a live instruction "
        "file; for this review it is the project's written rules.",
    ),
    "recall-consistency": ("inventory", ""),
    "precision-guarded-null": ("notify", ""),
    "precision-documented-exception": (
        "audit",
        "Treat `CONVENTIONS.fixture.md` as the project's written conventions for "
        "this area. It is named with a suffix only so it is not picked up as a "
        "live instruction file.",
    ),
    "single-pass": (
        "billing",
        "Run **only the correctness pass** (`--passes correctness`). Do not run "
        "the other three, and do not produce a merged four-pass report.",
    ),
}

# Traces from a real run showed the lead burning its turn budget inside Step 1
# -- `ls`, `find`, `Glob **/*`, `git rev-parse --is-inside-work-tree` -- trying
# to resolve a review target against a workspace that has no repository in it.
# In the worst run: two `sleep` calls and 705 seconds before it gave up, versus
# 135s and 243s for runs that stopped hunting in time. Same prompt, same
# plugin; the variance was entirely in how long it searched.
#
# Telling it "there is no repository" cut the turn count but left the long tail,
# because Step 1 still had to be attempted and abandoned. So the prompt now
# hands over a Review Packet that is already resolved and says to start at
# Step 2. There is nothing left to resolve, so there is nothing to flail at.
#
# `scaffold_script` in case.yaml would be the other way to fix this -- a real
# git repository in the workspace. The key passes schema validation on this CLI
# (2.1.277) but produced no files anywhere when run with --scaffold, so it is
# not usable yet. Revisit it: a real repo would also let the suite catch
# revision-dependent bugs, which it currently cannot see at all.
PACKET = """## Review Packet (already resolved -- do not rebuild it)

Target: the change below. Review base: the files as they were before this
change. Rule base: the same revision (this is not an incremental review).
Head: the files as given here. Repository root: not applicable.

This packet is complete. There is no git repository, no checkout and no files
on disk: nothing to clone, fetch, glob, `ls` or `git` at. Skip Step 1 of the
skill entirely -- the target is resolved, the changed files are listed, the
rule sources are named below, and the change intent is given. Go straight to
briefing and launching the reviewer passes, giving each the content below in
place of diff commands.

Time spent looking for files is time not spent reviewing, and there is nothing
to find.
"""

FRONTMATTER = """---
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash]
---
"""


def strip_annotations(text: str) -> str:
    """Drop `EVAL:` comment lines.

    They say which defect a fixture seeds, or that a fixture is bait. That is
    for whoever maintains the suite; leaving it in the prompt would hand the
    reviewer the answer and the case would measure nothing.
    """
    return "\n".join(ln for ln in text.splitlines() if "EVAL:" not in ln)


def fixture_files(name: str) -> list[tuple[str, str]]:
    d = os.path.join(FIXTURES, name)
    out = []
    for fn in sorted(os.listdir(d)):
        path = os.path.join(d, fn)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                out.append((fn, strip_annotations(fh.read())))
    return out


def build(case: str) -> str:
    fixture, extra = CASES[case]
    files = fixture_files(fixture)
    intent = next((t for n, t in files if n == "INTENT.md"), "")
    body = [FRONTMATTER]
    body.append("Run a four-pass code review of the change below.\n")
    if extra:
        body.append(extra + "\n")
    body.append(PACKET)
    body.append("Use the four-pass-review skill. Review the files as whole files: "
                "the change below is the whole of it.\n")
    body.append("## Change intent\n")
    body.append(intent.replace("# Change intent\n\n", "").strip() + "\n")
    body.append("## Files\n")
    for fn, text in files:
        if fn == "INTENT.md":
            continue
        lang = LANG.get(os.path.splitext(fn)[1], "")
        body.append(f"### `{fixture}/{fn}`\n")
        body.append(f"```{lang}\n{text.rstrip()}\n```\n")
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
