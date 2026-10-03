#!/usr/bin/env python3
"""Map what a change touches and what references it, without a model.

The deterministic half of impact. For every changed file it finds the
declarations the changed lines sit in (classes, methods, functions), whether
each was added, modified or removed and whether its signature line changed,
and every line in the repository that references it, at the revision where
that reference lives. References in files that are entry points by
convention (routes, console commands, the scheduler, jobs, listeners,
providers, config) are tagged with the kind of entry point.

It also decides whether there is anything to analyse: a change to docs,
tests, lockfiles or assets alone has no production impact to map, and the
skill stops before launching an agent.

    impact-scan.py --base <rev>                  base against the working tree,
                                                 including untracked files
    impact-scan.py --base <rev> --head <rev>     base against a commit
    impact-scan.py ... --impact-json             print a draft impact map in the
                                                 impact contract instead: direct
                                                 references only, unverified

What it cannot see is the point of the agent: a method called through the
container, a listener wired up by name, a route that names a controller as a
string. Declarations are found line by line with per-language patterns, and a
changed line is attributed to the nearest declaration above it, so a change
between two methods can be attributed to the first. Treat the output as
leads, not as the map.

Standard library only; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

REF_CAP = 40
CONSTRUCTORS = {"__construct", "__init__", "constructor", "initialize"}

CODE_EXT = {".php", ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go", ".rb",
            ".java", ".kt", ".cs", ".rs", ".vue", ".blade.php", ".sh", ".bash"}
CONFIG_EXT = {".json", ".yml", ".yaml", ".toml", ".ini", ".xml", ".neon", ".env"}
LOCKFILES = {"composer.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
             "poetry.lock", "Gemfile.lock", "go.sum", "Cargo.lock", "uv.lock"}
TEST_RES = [re.compile(p) for p in (
    r"(^|/)(tests?|spec|__tests__)/", r"Test\.php$", r"(^|/)test_[^/]+\.py$",
    r"_test\.(py|go|rb)$", r"\.(test|spec)\.[jt]sx?$", r"_spec\.rb$",
)]

# Where a reference lands -> what kind of entry point that file is, by
# convention. Laravel first; the common layouts of other frameworks after.
ENTRY_RULES = [
    ("schedule", r"^(routes/console\.php|app/Console/Kernel\.php)$"),
    ("http", r"^routes/(web|api|channels)\.php$|^routes/[^/]+\.php$"),
    ("http", r"^app/Http/(Middleware|Kernel)|^bootstrap/app\.php$"),
    ("console", r"^app/Console/Commands/"),
    ("queue", r"^app/Jobs/"),
    ("event", r"^app/(Listeners|Observers|Subscribers)/|^app/Providers/EventServiceProvider\.php$"),
    ("container", r"^app/Providers/"),
    ("config", r"^config/"),
    ("view", r"^resources/views/"),
    ("http", r"(^|/)urls\.py$|^config/routes\.rb$|(^|/)routes?(\.[jt]s|/)"),
]

# A changed file that is itself an entry point: the symbol in it is reached
# from outside the code, not by a caller grep can find.
SELF_ENTRY_RULES = [
    ("http", r"^app/Http/Controllers/"),
    ("console", r"^app/Console/Commands/"),
    ("queue", r"^app/Jobs/"),
    ("event", r"^app/(Listeners|Observers)/"),
    ("schedule", r"^(routes/console\.php|app/Console/Kernel\.php)$"),
    ("http", r"^routes/"),
]

PHP = {
    "class": re.compile(r"^\s*(?:(?:abstract|final|readonly)\s+)*(class|interface|trait|enum)\s+(\w+)"),
    "func": re.compile(r"^\s*(?:(?:public|protected|private|static|abstract|final)\s+)*function\s+&?(\w+)\s*\("),
}
PY = {
    "class": re.compile(r"^(\s*)class\s+(\w+)"),
    "func": re.compile(r"^(\s*)(?:async\s+)?def\s+(\w+)\s*\("),
}
JS = {
    "class": re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?(class)\s+(\w+)"),
    "func": re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)\s*\("
        r"|^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>"
        r"|^\s+(?:(?:public|private|protected|static|async|readonly|override)\s+)*(?!(?:if|for|while|switch|catch|return|function)\b)(\w+)\s*\([^)]*\)\s*(?::\s*[^{=]+)?\{\s*$"),
}
GO = {
    "class": re.compile(r"^type\s+(\w+)\s+(struct|interface)"),
    "func": re.compile(r"^func\s+(?:\(\s*\w+\s+\*?(\w+)\s*\)\s*)?(\w+)\s*\("),
}
RB = {
    "class": re.compile(r"^\s*(class|module)\s+([\w:]+)"),
    "func": re.compile(r"^\s*def\s+(?:self\.)?(\w+[?!=]?)"),
}


def language(path: str) -> str | None:
    if path.endswith(".php"):
        return "php"
    ext = os.path.splitext(path)[1]
    return {".py": "py", ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js",
            ".ts": "js", ".tsx": "js", ".vue": "js", ".go": "go", ".rb": "rb"}.get(ext)


def category(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    if name in LOCKFILES:
        return "other"
    if any(r.search(path) for r in TEST_RES):
        return "test"
    if path.endswith(".blade.php") or os.path.splitext(path)[1] in CODE_EXT:
        return "code"
    if os.path.splitext(path)[1] in CONFIG_EXT or name.startswith(".env"):
        return "config"
    if os.path.splitext(path)[1] in {".md", ".rst", ".txt", ".adoc"}:
        return "doc"
    return "other"


def _first(groups) -> str | None:
    return next((g for g in groups if g), None)


def declarations(path: str, text: str) -> list[dict]:
    """Declarations in a file, in order: {line, kind, name, cls, indent, sig}."""
    lang = language(path)
    if lang is None or path.endswith(".blade.php"):
        return []
    rules = {"php": PHP, "py": PY, "js": JS, "go": GO, "rb": RB}[lang]
    out, cls, cls_indent = [], None, -1
    for i, raw in enumerate(text.splitlines(), start=1):
        indent = len(raw) - len(raw.lstrip())
        # A class ends at the first line back at its own indentation: `}`,
        # `end`, a dedent, or the next top-level declaration. PSR-12 puts the
        # opening brace on its own line at that indentation; that is not an end.
        if cls is not None and raw.strip() and indent <= cls_indent and raw.strip() != "{" \
                and not rules["class"].match(raw):
            cls, cls_indent = None, -1
        m = rules["class"].match(raw)
        if m:
            name = m.group(1) if lang == "go" else m.group(2)
            cls, cls_indent = name, indent
            out.append({"line": i, "kind": "class", "name": name, "cls": None,
                        "indent": indent, "sig": raw.strip()})
            continue
        m = rules["func"].match(raw)
        if m:
            if lang == "go":
                owner, name = m.group(1), m.group(2)
            elif lang == "py":
                owner, name = None, m.group(2)
            else:
                owner, name = None, _first(m.groups())
            if not name:
                continue
            if lang != "go":
                owner = cls if (cls is not None and indent > cls_indent) else None
            out.append({"line": i, "kind": "method" if owner else "function", "name": name,
                        "cls": owner, "indent": indent, "sig": raw.strip()})
    return out


def symbol_name(decl: dict) -> str:
    return f"{decl['cls']}::{decl['name']}" if decl.get("cls") else decl["name"]


def enclosing(decls: list[dict], line: int, lines: list[str], lang: str | None) -> dict | None:
    """The innermost declaration a line belongs to, or None at file level."""
    best = None
    for d in decls:
        if d["line"] > line:
            break
        best = d
    if best is None:
        return None
    if lang == "py" and best["line"] != line and 0 < line <= len(lines):
        raw = lines[line - 1]
        indent = len(raw) - len(raw.lstrip())
        # In Python a line at or left of the def's own indentation is outside it.
        if raw.strip() and indent <= best["indent"]:
            outer = [d for d in decls if d["line"] < line and d["indent"] < indent]
            return outer[-1] if outer else None
    return best


def changed_lines(diff: str) -> dict[str, dict[str, set]]:
    """`git diff -U0` -> {path: {"head": {lines}, "base": {lines}, "base_path": p}}."""
    out: dict[str, dict] = {}
    cur = base_path = None
    for line in diff.splitlines():
        if line.startswith("--- "):
            raw = line[4:]
            base_path = None if raw == "/dev/null" else (raw[2:] if raw.startswith("a/") else raw)
        elif line.startswith("+++ "):
            head = line[4:]
            cur = base_path if head == "/dev/null" else (head[2:] if head.startswith("b/") else head)
            out.setdefault(cur, {"head": set(), "base": set(), "base_path": base_path})
        elif line.startswith("@@") and cur is not None:
            m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if not m:
                continue
            b0, bn = int(m.group(1)), int(m.group(2) or 1)
            h0, hn = int(m.group(3)), int(m.group(4) or 1)
            out[cur]["base"].update(range(b0, b0 + bn))
            out[cur]["head"].update(range(h0, h0 + hn))
    return out


def entry_kind(path: str, rules=ENTRY_RULES) -> str | None:
    for kind, pattern in rules:
        if re.search(pattern, path):
            return kind
    return None


def reference_filter(name: str, kind: str):
    """A predicate keeping lines that use `name` the way a reference would."""
    n = re.escape(name.split("::")[-1])
    if kind == "class":
        use = re.compile(rf"(?<![\w$]){n}(?![\w$])")
    else:
        use = re.compile(rf"(->|\?->|::|\.)\s*{n}\s*\(|(?<![\w$>:.]){n}\s*\(|['\"@]{n}['\"]")
    definition = re.compile(rf"\b(function|def|func|class|interface|trait|enum)\s+&?{n}\b")
    return lambda text: bool(use.search(text)) and not definition.search(text)


def scan(base_files: dict[str, str], head_files: dict[str, str], diff: str,
         search, untracked: list[str] | None = None) -> dict:
    """The core, independent of git so tests and evals can drive it.

    base_files/head_files map a path to its text at each revision, for the
    changed files at least. `search(name, rev)` returns (path, line, text)
    for every line containing `name` as a word at `rev` ("base" or "head").
    """
    changes = changed_lines(diff)
    for p in untracked or []:
        n = len(head_files.get(p, "").splitlines()) or 1
        changes[p] = {"head": set(range(1, n + 1)), "base": set(), "base_path": None}

    files, symbols, seen = [], [], {}
    for path, ch in sorted(changes.items()):
        if path is None:
            continue
        in_head, in_base = path in head_files, (ch["base_path"] or path) in base_files
        status = "added" if not in_base else ("deleted" if not in_head else "modified")
        cat = category(path)
        files.append({"path": path, "status": status, "category": cat,
                      "lines_changed": len(ch["head"]) + len(ch["base"])})
        if cat != "code":
            continue
        lang = language(path)
        for rev, text, lines_hit in (("head", head_files.get(path), ch["head"]),
                                     ("base", base_files.get(ch["base_path"] or path), ch["base"])):
            if text is None:
                continue
            decls, lines = declarations(path, text), text.splitlines()
            for ln in sorted(lines_hit):
                d = enclosing(decls, ln, lines, lang)
                key = (path, symbol_name(d) if d else "")
                if key in seen:
                    continue
                seen[key] = {"decl": d, "rev": rev}

    base_decls = {p: {symbol_name(d): d for d in declarations(p, t)} for p, t in base_files.items()}
    head_decls = {p: {symbol_name(d): d for d in declarations(p, t)} for p, t in head_files.items()}
    for i, ((path, name), info) in enumerate(sorted(seen.items(), key=lambda kv: kv[0]), start=1):
        d = info["decl"]
        if d is None:
            symbols.append({"id": f"S{i}", "symbol": path, "kind": "file", "change": "modified",
                            "signature_changed": False, "path": path, "line": 1,
                            "references": [], "total_references": 0, "truncated": False})
            continue
        bpath = changes.get(path, {}).get("base_path") or path
        b, h = base_decls.get(bpath, {}).get(name), head_decls.get(path, {}).get(name)
        change = "added" if b is None else ("removed" if h is None else "modified")
        anchor = h or b
        refs = []
        # A constructor is reached wherever its class is built or type-hinted,
        # and its own name matches every constructor in the codebase.
        term, term_kind = d["name"], d["kind"]
        if d["kind"] == "method" and d["name"] in CONSTRUCTORS and d.get("cls"):
            term, term_kind = d["cls"], "class"
        keep = reference_filter(term, term_kind)
        # Head references are what the change affects. For a removed symbol,
        # any head reference left is dangling, and its base references show
        # who used to depend on it.
        for rev in (("head", "base") if change == "removed" else ("head",)):
            for rpath, rline, rtext in search(term, rev):
                if rpath in (path, bpath) and rline == anchor["line"]:
                    continue
                if not keep(rtext):
                    continue
                refs.append({"path": rpath, "line": rline, "text": rtext.strip()[:160],
                             "rev": rev, "in_test": category(rpath) == "test",
                             "entry_hint": entry_kind(rpath)})
        symbols.append({
            "id": f"S{i}", "symbol": name, "kind": d["kind"], "change": change,
            "signature_changed": bool(b and h and b["sig"] != h["sig"]),
            "path": path, "line": anchor["line"],
            "entry": entry_kind(path, SELF_ENTRY_RULES),
            "references": refs[:REF_CAP], "total_references": len(refs),
            "truncated": len(refs) > REF_CAP,
        })

    analysable = [f for f in files if f["category"] in ("code", "config")]
    reason = ("code or config changed" if analysable else
              "only " + ", ".join(sorted({f["category"] for f in files}) or ["nothing"]) + " changed")
    return {"analyse": bool(analysable), "reason": reason, "files": files, "symbols": symbols}


def to_impact(result: dict, target: str, base: str, head: str) -> dict:
    """A draft impact map from the scan alone: direct references, nothing verified."""
    changed = [{"symbol": s["symbol"], "kind": s["kind"], "change": s["change"],
                "signature_changed": s["signature_changed"], "path": s["path"], "line": s["line"]}
               for s in result["symbols"]]
    callers, entries, covering, reached = [], {}, {}, set()
    for s in result["symbols"]:
        if s.get("entry"):
            entries.setdefault((s["entry"], s["path"], s["line"]),
                               {"kind": s["entry"], "name": s["symbol"], "path": s["path"],
                                "line": s["line"], "reaches": []})["reaches"].append(s["symbol"])
        for r in s["references"]:
            if r["in_test"]:
                covering.setdefault(r["path"], set()).add(s["symbol"])
                reached.add(s["symbol"])
                continue
            callers.append({"target": s["symbol"], "path": r["path"], "line": r["line"],
                            "via": "", "hops": 1, "verified": False})
            if r["entry_hint"]:
                key = (r["entry_hint"], r["path"], r["line"])
                entries.setdefault(key, {"kind": r["entry_hint"], "name": r["text"][:120],
                                         "path": r["path"], "line": r["line"],
                                         "reaches": []})["reaches"].append(s["symbol"])
    limits = ["Draft from impact-scan.py alone: direct references found by name, unverified. "
              "Name collisions are not removed, callers of callers are not followed, and "
              "anything wired up by configuration or by string is missing."]
    limits += [f"{s['symbol']}: {s['total_references']} references, only the first "
               f"{REF_CAP} kept" for s in result["symbols"] if s["truncated"]]
    return {
        "version": 1, "target": target, "base": base, "head": head, "mode": "quick",
        "changed": changed, "callers": callers, "entry_points": list(entries.values()),
        "tests": {"covering": [{"path": p, "reaches": sorted(v)} for p, v in sorted(covering.items())],
                  "uncovered": sorted(s["symbol"] for s in result["symbols"]
                                      if s["symbol"] not in reached and s["kind"] != "file"
                                      and s["change"] != "removed")},
        "data": [], "contracts": [], "risks": [], "limits": limits,
    }


def git(*args: str) -> str:
    try:
        res = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"cannot run git: {exc}") from exc
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def git_search(base: str, head: str | None):
    def search(name: str, rev: str):
        refspec = base if rev == "base" else head
        # With no revision this searches the working tree, and --untracked
        # includes a file just created and not yet added.
        args = (["grep", "-n", "-I", "-w", "-F", "-e", name]
                + ([refspec] if refspec else ["--untracked"]))
        try:
            res = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
        except OSError:
            return []
        out = []
        for line in res.stdout.splitlines():
            if refspec:
                line = line[len(refspec) + 1:]  # "<rev>:path:line:text"
            parts = line.split(":", 2)
            if len(parts) == 3 and parts[1].isdigit():
                out.append((parts[0], int(parts[1]), parts[2]))
        return out
    return search


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", required=True, help="the revision the change is taken against")
    ap.add_argument("--head", help="the head revision; omit for the working tree")
    ap.add_argument("--target", help="a description of the target, for --impact-json")
    ap.add_argument("--impact-json", action="store_true",
                    help="print a draft impact map in the impact contract instead of the scan")
    args = ap.parse_args(argv)

    try:
        diff = git("diff", "-U0", "-M", "--no-color", args.base, *([args.head] if args.head else []))
        untracked = [] if args.head else [p for p in git("ls-files", "--others", "--exclude-standard").splitlines()]
        changes = changed_lines(diff)
        paths = {p for p in changes if p} | set(untracked)
        base_files, head_files = {}, {}
        for p in paths:
            bp = changes.get(p, {}).get("base_path") or p
            try:
                base_files[bp] = git("show", f"{args.base}:{bp}")
            except RuntimeError:
                pass
            if args.head:
                try:
                    head_files[p] = git("show", f"{args.head}:{p}")
                except RuntimeError:
                    pass
            elif os.path.isfile(p):
                with open(p, encoding="utf-8", errors="replace") as fh:
                    head_files[p] = fh.read()
        result = scan(base_files, head_files, diff, git_search(args.base, args.head), untracked)
    except (OSError, RuntimeError) as exc:
        print(f"impact-scan: {exc}", file=sys.stderr)
        return 1

    head = args.head or "working tree"
    if args.impact_json:
        print(json.dumps(to_impact(result, args.target or f"{args.base}...{head}", args.base, head), indent=2))
    else:
        out = {"base": args.base, "head": head}
        out.update(result)
        print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
