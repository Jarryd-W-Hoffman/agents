#!/usr/bin/env python3
"""Find the database migrations in a change, without a model.

This is what makes the plugin cheap to run on every change: when the change
touches no migration, the skill stops here and no agent is launched.

Prints one JSON object describing what the reviewer needs:

    {
      "base": "<rev>", "head": "<rev>" | "working tree",
      "migrations": [
        {"path": "database/migrations/2026_10_01_000000_x.php",
         "status": "added" | "modified" | "deleted" | "renamed",
         "old_path": "...",               only when renamed
         "framework": "laravel",
         "out_of_order": true}            only when it sorts before a migration
                                          that already existed at base
      ],
      "frameworks": ["laravel"],
      "schema_files": [...],              schema dumps at base (database/schema/*.sql, db/schema.rb, ...)
      "deploy_files": [...],              deploy and database config at base
      "rule_files": [...]                 CLAUDE.md, AGENTS.md, .claude/rules/*.md at base
    }

A migration that is modified, deleted or renamed already existed at base, and
has most likely already run in production. That status is a finding signal in
itself: editing a migration that has run changes fresh installs and nothing
else.

Usage:
    find-migrations.py --base <rev>                 base against the working tree,
                                                    including untracked files
    find-migrations.py --base <rev> --head <rev>    base against a commit
    find-migrations.py --name-status F --base-files G [--untracked H]
                                                    offline: read what git would
                                                    have printed from files

Standard library only; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

# (framework, pattern) in order; the first match wins. More specific layouts
# come first: alembic's versions/*.py before django's migrations/*.py, and
# prisma's migration.sql before the generic SQL rule.
MIGRATION_RULES = [
    ("prisma", r"(^|/)prisma/migrations/[^/]+/migration\.sql$"),
    ("alembic", r"(^|/)(alembic|migrations)/versions/[^/]+\.py$"),
    ("django", r"(^|/)migrations/\d{4}_[^/]+\.py$"),
    ("rails", r"(^|/)db/migrate/[^/]+\.rb$"),
    ("flyway", r"(^|/)db/migration/[^/]*V\d[^/]*__[^/]+\.sql$"),
    ("laravel", r"(?i)(^|/)(database/)?migrations/[^/]+\.php$"),
    ("sql", r"(^|/)migrations?/[^/]+\.sql$"),
    ("node", r"(^|/)migrations/[^/]+\.(js|ts|mjs|cjs)$"),
]

SCHEMA_RULES = [
    r"(^|/)database/schema/[^/]+\.(sql|dump)$",
    r"(^|/)db/(schema\.rb|structure\.sql)$",
    r"(^|/)prisma/schema\.prisma$",
    r"(^|/)schema\.sql$",
]

DEPLOY_RULES = [
    r"^deploy\.php$",
    r"(?i)^envoy\.blade\.php$",
    r"(?i)^\.github/workflows/[^/]*(deploy|release)[^/]*\.ya?ml$",
    r"^\.gitlab-ci\.yml$",
    r"^(Procfile|fly\.toml|render\.yaml|vapor\.yml|app\.yaml)$",
    r"^config/database\.php$",
    r"^\.env\.example$",
    r"(?i)^docs/[^/]*deploy[^/]*\.md$",
]

RULE_RULES = [
    r"(^|/)CLAUDE\.md$",
    r"^AGENTS\.md$",
    r"^\.claude/rules/[^/]+\.md$",
]

# Leading version of a migration filename, by framework, as a sortable tuple.
# Frameworks whose order is a dependency graph (django, alembic) have none.
VERSION_RES = {
    "laravel": re.compile(r"^(\d{4})_(\d{2})_(\d{2})_(\d{6})_"),
    "rails": re.compile(r"^(\d{14})_"),
    "flyway": re.compile(r"^V(\d+(?:[._]\d+)*)__"),
    "prisma": re.compile(r"^(\d{14})_"),
}

STATUS = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed",
          "C": "added", "T": "modified"}


def framework_of(path: str) -> str | None:
    if path.endswith("/__init__.py"):
        return None
    for name, pattern in MIGRATION_RULES:
        if re.search(pattern, path):
            return name
    return None


def _version(framework: str, path: str):
    rx = VERSION_RES.get(framework)
    if rx is None:
        return None
    # prisma versions the directory, not the file
    name = path.split("/")[-2] if framework == "prisma" else path.split("/")[-1]
    m = rx.match(name)
    if not m:
        return None
    return tuple(int(p) for g in m.groups() for p in re.split(r"[._]", g))


def _parent(path: str, framework: str) -> str:
    parts = path.split("/")
    return "/".join(parts[:-2] if framework == "prisma" else parts[:-1])


def parse_name_status(text: str) -> list[tuple[str, str, str | None]]:
    """`git diff --name-status -M` lines -> (status letter, path, old path or None)."""
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        letter = fields[0][:1]
        if letter in ("R", "C") and len(fields) >= 3:
            out.append((letter, fields[2], fields[1]))
        elif len(fields) >= 2:
            out.append((letter, fields[1], None))
    return out


def classify(name_status: str, base_files: list[str], untracked: list[str] | None = None) -> dict:
    changes = parse_name_status(name_status)
    changes += [("A", p, None) for p in (untracked or [])]

    # Newest version already present at base, per migrations directory.
    newest: dict[tuple[str, str], tuple] = {}
    for path in base_files:
        fw = framework_of(path)
        v = _version(fw, path) if fw else None
        if v is not None:
            key = (fw, _parent(path, fw))
            if key not in newest or v > newest[key]:
                newest[key] = v

    migrations, seen = [], set()
    for letter, path, old in changes:
        fw = framework_of(path) or (framework_of(old) if old else None)
        if fw is None or path in seen:
            continue
        seen.add(path)
        entry = {"path": path, "status": STATUS.get(letter, "modified"), "framework": fw}
        if old:
            entry["old_path"] = old
        v = _version(fw, path)
        top = newest.get((fw, _parent(path, fw)))
        if entry["status"] == "added" and v is not None and top is not None and v < top:
            entry["out_of_order"] = True
        migrations.append(entry)

    def matching(rules):
        return sorted(p for p in base_files if any(re.search(r, p) for r in rules))

    return {
        "migrations": migrations,
        "frameworks": sorted({m["framework"] for m in migrations}),
        "schema_files": matching(SCHEMA_RULES),
        "deploy_files": matching(DEPLOY_RULES),
        "rule_files": matching(RULE_RULES),
    }


def git(*args: str) -> str:
    try:
        res = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"cannot run git: {exc}") from exc
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", help="the revision the change is taken against")
    ap.add_argument("--head", help="the head revision; omit for the working tree")
    ap.add_argument("--name-status", help="offline: a file of `git diff --name-status -M` output")
    ap.add_argument("--base-files", help="offline: a file of `git ls-tree -r --name-only <base>` output")
    ap.add_argument("--untracked", help="offline: a file of untracked paths, one per line")
    args = ap.parse_args(argv)

    try:
        if args.name_status:
            if not args.base_files:
                ap.error("--name-status needs --base-files")
            name_status = _read(args.name_status)
            base_files = _read(args.base_files).splitlines()
            untracked = _read(args.untracked).splitlines() if args.untracked else []
            base, head = args.base or "(offline)", args.head or "(offline)"
        else:
            if not args.base:
                ap.error("--base is required unless --name-status is given")
            base = args.base
            head = args.head or "working tree"
            diff_args = ["diff", "--name-status", "-M", base] + ([args.head] if args.head else [])
            name_status = git(*diff_args)
            base_files = git("ls-tree", "-r", "--name-only", base).splitlines()
            # A migration just generated with `make:migration` is untracked
            # until it is added, and is exactly the file to review.
            untracked = ([] if args.head else
                         git("ls-files", "--others", "--exclude-standard").splitlines())
    except (OSError, RuntimeError) as exc:
        print(f"find-migrations: {exc}", file=sys.stderr)
        return 1

    result = {"base": base, "head": head}
    result.update(classify(name_status, base_files, untracked))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
