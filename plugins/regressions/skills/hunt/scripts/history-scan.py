#!/usr/bin/env python3
"""Find the history a change could regress, without a model.

The deterministic half of regressions. For every changed file it reads
the history *before* the change, at the base revision:

- the commits that last touched the changed lines (`git log -L`), and which
  of them were fixes or reverts, with any issue references they carry;
- other commits on the file that were fixes or reverts;
- files that almost always change together with this one and are missing
  from this change.

It also decides whether there is anything to look at. A change whose lines
no fix or revert ever touched, on files no revert touched, with no usual
partner missing, has no history to regress, and the skill stops before
launching an agent.

    history-scan.py --base <rev>                  base against the working tree
    history-scan.py --base <rev> --head <rev>     base against a commit

Signals, not findings: a fix commit on the changed lines says "look here",
not "this is a regression". The agent reads the commits and decides.

Standard library only; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

COMMITS_PER_FILE = 15
FILE_LOG_DEPTH = 200
COCHANGE_DEPTH = 1000
HUNKS_PER_FILE = 12
PARTNER_MIN = 3
PARTNER_RATIO = 0.6

FIX_RE = re.compile(r"\b(fix(es|ed)?|bug|hotfix|regression|patch(ed)?|broke(n)?|crash(es|ed)?|"
                    r"incident|outage|security|vuln(erability)?|cve)\b", re.I)
REVERT_SUBJECT_RE = re.compile(r'^Revert\b', re.I)
REVERTS_RE = re.compile(r"This reverts commit ([0-9a-f]{7,40})")
REF_RE = re.compile(r"(?<![\w/])(#\d+|[A-Z][A-Z0-9]+-\d+|GH-\d+)\b")

DOC_EXT = {".md", ".rst", ".txt", ".adoc"}
ASSET_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".woff", ".woff2", ".ttf", ".eot"}
LOCKFILES = {"composer.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
             "poetry.lock", "Gemfile.lock", "go.sum", "Cargo.lock", "uv.lock"}

SEP, END = "\x1f", "\x1e"


def reviewable(path: str) -> bool:
    """Files whose history can be regressed: everything but docs, assets and lockfiles."""
    name = path.rsplit("/", 1)[-1]
    ext = os.path.splitext(name)[1].lower()
    return not (name in LOCKFILES or ext in DOC_EXT or ext in ASSET_EXT
                or path.startswith("docs/") or name.startswith("LICENSE"))


def git(*args: str, check: bool = True) -> str:
    try:
        res = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"cannot run git: {exc}") from exc
    if res.returncode != 0:
        if check:
            raise RuntimeError(f"git {' '.join(args)}: {res.stderr.strip()}")
        return ""
    return res.stdout


def hunks(diff: str) -> dict[str, dict]:
    """`git diff -U0` -> {head path: {"base_path": p or None, "ranges": [(start, end)] at base}}.

    A pure insertion has no base lines; it is given the two lines either side
    of where it lands, so the history of what surrounds it is still read.
    """
    out: dict[str, dict] = {}
    cur = base_path = None
    for line in diff.splitlines():
        if line.startswith("--- "):
            raw = line[4:]
            base_path = None if raw == "/dev/null" else (raw[2:] if raw.startswith("a/") else raw)
        elif line.startswith("+++ "):
            raw = line[4:]
            cur = base_path if raw == "/dev/null" else (raw[2:] if raw.startswith("b/") else raw)
            out.setdefault(cur, {"base_path": base_path, "ranges": []})
        elif line.startswith("@@") and cur is not None:
            m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if not m:
                continue
            start, count = int(m.group(1)), int(m.group(2) or 1)
            if count == 0:
                out[cur]["ranges"].append((max(1, start - 1), start + 2))
            else:
                out[cur]["ranges"].append((start, start + count - 1))
    return out


def classify(subject: str, body: str) -> tuple[list[str], str | None, list[str]]:
    """(kinds, reverted sha, refs) for one commit message."""
    kinds, reverted = [], None
    m = REVERTS_RE.search(body)
    if REVERT_SUBJECT_RE.search(subject) or m:
        kinds.append("revert")
        reverted = m.group(1) if m else None
    if FIX_RE.search(subject) or FIX_RE.search(body):
        kinds.append("fix")
    refs = sorted(set(REF_RE.findall(subject + "\n" + body)))
    return kinds, reverted, refs


def commit_info(sha: str) -> dict:
    raw = git("show", "-s", f"--format=%H{SEP}%h{SEP}%ad{SEP}%an{SEP}%s{SEP}%b", "--date=short", sha)
    full, short, date, author, subject, body = (raw.rstrip("\n").split(SEP, 5) + [""] * 6)[:6]
    kinds, reverted, refs = classify(subject, body)
    info = {"sha": full, "short": short, "date": date, "author": author, "subject": subject,
            "kinds": kinds, "refs": refs}
    if reverted:
        info["reverts"] = reverted
    return info


def line_commits(base: str, path: str, ranges: list[tuple[int, int]], length: int) -> set[str]:
    """Commits that touched any of these line ranges of `path`, as of `base`."""
    shas: set[str] = set()
    for start, end in ranges[:HUNKS_PER_FILE]:
        start, end = min(start, length), min(end, length)
        if length == 0 or start < 1:
            continue
        out = git("log", f"-L{start},{end}:{path}", "-s", "--format=%H", base, check=False)
        shas.update(s for s in out.split() if re.fullmatch(r"[0-9a-f]{40}", s))
    return shas


def cochange_index(base: str) -> dict[str, list[str]]:
    """Commit -> the files it touched, over the most recent commits at base."""
    out = git("log", f"-n{COCHANGE_DEPTH}", "--name-only", f"--format={END}%H", base, check=False)
    index: dict[str, list[str]] = {}
    for block in out.split(END):
        lines = [ln for ln in block.strip().splitlines() if ln]
        if lines:
            index[lines[0]] = lines[1:]
    return index


def missing_partners(path: str, changed: set[str], index: dict[str, list[str]],
                     base_files: set[str]) -> list[dict]:
    with_file = [files for files in index.values() if path in files]
    if len(with_file) < PARTNER_MIN:
        return []
    counts: dict[str, int] = {}
    for files in with_file:
        for f in set(files) - {path}:
            counts[f] = counts.get(f, 0) + 1
    out = []
    for f, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if (n >= PARTNER_MIN and n / len(with_file) >= PARTNER_RATIO and f not in changed
                and f in base_files and reviewable(f)):
            out.append({"path": f, "together": n, "of": len(with_file)})
    return out[:5]


def rank(info: dict) -> int:
    """How telling a commit is; sorted stably after newest-first, so ties stay newest first."""
    if info["on_changed_lines"] and info["kinds"]:
        return 0
    if "revert" in info["kinds"]:
        return 1
    if "fix" in info["kinds"]:
        return 2
    return 3


def scan(base: str, head: str | None) -> dict:
    diff = git("diff", "-U0", "-M", "--no-color", base, *([head] if head else []))
    changes = hunks(diff)
    base_files = set(git("ls-tree", "-r", "--name-only", base, check=False).splitlines())
    changed = set(changes) | {c["base_path"] for c in changes.values() if c["base_path"]}
    index = cochange_index(base)
    files, totals = [], {"fix_on_lines": 0, "reverts": 0, "missing_partners": 0}

    for path, ch in sorted((p, c) for p, c in changes.items() if p):
        bpath = ch["base_path"] or path
        entry = {"path": path, "reviewed": reviewable(path), "commits": [], "missing_partners": []}
        if bpath != path:
            entry["base_path"] = bpath
        if not entry["reviewed"] or bpath not in base_files:
            entry["history_commits"] = 0
            if bpath not in base_files:
                entry["note"] = "new file: no history at base"
            files.append(entry)
            continue
        length = len(git("show", f"{base}:{bpath}", check=False).splitlines())
        on_lines = line_commits(base, bpath, ch["ranges"], length)
        file_log = git("log", f"-n{FILE_LOG_DEPTH}", "--format=%H", base, "--", bpath, check=False).split()
        entry["history_commits"] = len(file_log)
        infos = []
        for sha in dict.fromkeys(list(on_lines) + file_log):
            info = commit_info(sha)
            info["on_changed_lines"] = sha in on_lines
            if info["kinds"] or info["on_changed_lines"]:
                infos.append(info)
        # Most telling first: a fix or revert on the changed lines, then any
        # revert, any fix, then plain commits on the lines, newest first.
        infos.sort(key=lambda i: i["date"], reverse=True)
        infos.sort(key=rank)
        entry["commits"] = infos[:COMMITS_PER_FILE]
        entry["missing_partners"] = missing_partners(bpath, changed, index, base_files)
        totals["fix_on_lines"] += sum(1 for i in infos if i["on_changed_lines"] and i["kinds"])
        totals["reverts"] += sum(1 for i in infos if "revert" in i["kinds"])
        totals["missing_partners"] += len(entry["missing_partners"])
        files.append(entry)

    analyse = any(totals.values())
    if analyse:
        reason = (f"{totals['fix_on_lines']} fix or revert commit(s) on the changed lines, "
                  f"{totals['reverts']} revert(s) on the changed files, "
                  f"{totals['missing_partners']} usual partner file(s) missing")
    elif not any(f["reviewed"] for f in files):
        reason = "only docs, assets or lockfiles changed"
    else:
        reason = "no fix or revert touched the changed lines, no revert touched the files, no usual partner is missing"
    return {"analyse": analyse, "reason": reason, "signals": totals, "files": files}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", required=True, help="the revision the change is taken against")
    ap.add_argument("--head", help="the head revision; omit for the working tree")
    args = ap.parse_args(argv)
    try:
        result = scan(args.base, args.head)
    except (OSError, RuntimeError) as exc:
        print(f"history-scan: {exc}", file=sys.stderr)
        return 1
    out = {"base": args.base, "head": args.head or "working tree"}
    out.update(result)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
