#!/usr/bin/env python3
"""Build a real git repository from a fixture, deterministically.

A fixture is a directory:

    commits/
      01-initial/           MESSAGE (the commit message) and the files the
      02-fix-double-charge/ commit adds or changes; DELETE lists paths it
      ...                   removes, one per line
    (a MESSAGE may name an earlier commit as {{SHA:NN}}, e.g. in a revert)
    head/                   files changed in the working tree after the last
                            commit: the change under review
    INTENT.md               the change's stated intent

Every commit gets the same author and a fixed date one day after the last, so
the same fixture always produces the same SHAs. That is what lets the eval
prompts, which quote SHAs, be generated and checked in CI.

Used by evals/build_prompts.py and tests/test_history_scan.py.
Standard library only; no third-party dependencies.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess

AUTHOR = "Dev Example"
EMAIL = "dev@example.com"


def _git(repo: str, *args: str, env: dict | None = None) -> str:
    res = subprocess.run(["git", "-C", repo, "-c", "commit.gpgsign=false", *args],
                         capture_output=True, text=True, env=env, check=True)
    return res.stdout


def _overlay(src: str, dst: str) -> None:
    for root, _, names in os.walk(src):
        for n in names:
            if n in ("MESSAGE", "DELETE"):
                continue
            rel = os.path.relpath(os.path.join(root, n), src)
            target = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(os.path.join(root, n), target)


def build(fixture: str, repo: str, strip=None) -> list[str]:
    """Create `repo` from `fixture`; return the SHAs of its commits, oldest first.

    `strip`, if given, is applied to every file's text before it is written,
    so maintainer annotations never reach the repository's history.
    """
    os.makedirs(repo, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True, capture_output=True)
    commits_dir = os.path.join(fixture, "commits")
    shas = []
    for day, name in enumerate(sorted(os.listdir(commits_dir)), start=1):
        src = os.path.join(commits_dir, name)
        _overlay(src, repo)
        delete = os.path.join(src, "DELETE")
        if os.path.exists(delete):
            with open(delete, encoding="utf-8") as fh:
                for rel in filter(None, (ln.strip() for ln in fh)):
                    os.remove(os.path.join(repo, rel))
        if strip:
            _strip_tree(repo, strip)
        with open(os.path.join(src, "MESSAGE"), encoding="utf-8") as fh:
            message = fh.read().strip() + "\n"
        # A revert names the commit it reverts, whose SHA only exists once
        # that commit does: {{SHA:02}} is the second commit's full SHA.
        message = re.sub(r"\{\{SHA:(\d+)\}\}", lambda m: shas[int(m.group(1)) - 1], message)
        date = f"2026-01-{day:02d}T10:00:00+0000" if day <= 28 else f"2026-02-{day - 28:02d}T10:00:00+0000"
        env = dict(os.environ, GIT_AUTHOR_NAME=AUTHOR, GIT_AUTHOR_EMAIL=EMAIL, GIT_COMMITTER_NAME=AUTHOR,
                   GIT_COMMITTER_EMAIL=EMAIL, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        _git(repo, "add", "-A", env=env)
        _git(repo, "commit", "-q", "-m", message, env=env)
        shas.append(_git(repo, "rev-parse", "HEAD").strip())
    head = os.path.join(fixture, "head")
    if os.path.isdir(head):
        _overlay(head, repo)
        if strip:
            _strip_tree(repo, strip)
    return shas


def _strip_tree(repo: str, strip) -> None:
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d != ".git"]
        for n in names:
            path = os.path.join(root, n)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            new = strip(text)
            if new != text:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(new)
