#!/usr/bin/env python3
"""Survey a repository for the docs skills, with no model.

Prints one JSON object describing what a README and a user manual need to
know before anyone reads the code: the project's name and remote, its stacks
and how each is run, tested and built, the CI workflows (for badges), the
licence, the documentation that already exists, the images it already uses,
and whether the project has something to take screenshots of.

    python3 survey.py [--root <dir>]

Everything here is a guess from file names and manifests. The skills treat it
as a starting point to verify, never as the answer.

Standard library only; runs on Python 3.9.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", "target", ".venv",
             "venv", "__pycache__", ".next", ".nuxt", "storage", "coverage",
             ".idea", ".vscode", "tmp"}

LICENCES = (
    ("MIT", r"\bMIT License\b|Permission is hereby granted, free of charge"),
    ("Apache-2.0", r"Apache License,?\s+Version 2\.0"),
    ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
    ("AGPL-3.0", r"GNU AFFERO GENERAL PUBLIC LICENSE"),
    ("BSD-3-Clause", r"Redistribution and use in source and binary forms"),
    ("MPL-2.0", r"Mozilla Public License,? v(?:ersion)? 2\.0"),
)


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def load_json(path: str) -> dict:
    try:
        data = json.loads(read(path))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def git(root: str, *args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", root, *args], capture_output=True,
                             text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def github_slug(remote: str) -> str | None:
    m = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", remote)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def walk(root: str, max_depth: int = 4):
    """Yield repository-relative file paths, skipping dependency and build dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        dirnames[:] = sorted(d for d in dirnames
                             if d not in SKIP_DIRS and not (depth == 0 and d.startswith(".")
                                                            and d not in (".github",)))
        if depth >= max_depth:
            dirnames[:] = []
        for name in sorted(filenames):
            yield os.path.normpath(os.path.join(rel, name))


# --------------------------------------------------------------------------
# Stacks
# --------------------------------------------------------------------------

def node_stack(root: str) -> dict | None:
    pkg = load_json(os.path.join(root, "package.json"))
    if not pkg and not os.path.isfile(os.path.join(root, "package.json")):
        return None
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    manager = "npm"
    for lock, name in (("bun.lock", "bun"), ("bun.lockb", "bun"), ("pnpm-lock.yaml", "pnpm"),
                       ("yarn.lock", "yarn")):
        if os.path.isfile(os.path.join(root, lock)):
            manager = name
            break
    scripts = pkg.get("scripts", {}) if isinstance(pkg.get("scripts"), dict) else {}
    frameworks = [f for f in ("react", "vue", "svelte", "next", "nuxt", "vite", "electron",
                              "express", "fastify", "hono", "@inertiajs/react", "three",
                              "cesium", "playwright", "@playwright/test", "playwright-core",
                              "vitest", "jest", "typescript") if f in deps]
    run = "run " if manager in ("npm", "bun", "pnpm") else ""
    commands = {k: f"{manager} {run}{k}".replace("npm run test", "npm test")
                for k in scripts if k in ("dev", "start", "serve", "build", "test", "lint",
                                          "preview", "format", "typecheck", "check")}
    return {"stack": "node", "name": pkg.get("name"), "description": pkg.get("description"),
            "version": pkg.get("version"), "manager": manager, "frameworks": frameworks,
            "bin": sorted(pkg["bin"]) if isinstance(pkg.get("bin"), dict) else
            ([pkg["name"]] if isinstance(pkg.get("bin"), str) and pkg.get("name") else []),
            "engines": pkg.get("engines", {}), "commands": commands}


def php_stack(root: str) -> dict | None:
    composer = load_json(os.path.join(root, "composer.json"))
    if not composer:
        return None
    req = {**composer.get("require", {}), **composer.get("require-dev", {})}
    frameworks = [f for f in ("laravel/framework", "inertiajs/inertia-laravel", "livewire/livewire",
                              "filament/filament", "nativephp/electron", "nativephp/desktop",
                              "pestphp/pest", "phpunit/phpunit", "larastan/larastan",
                              "phpstan/phpstan", "laravel/pint", "rector/rector",
                              "symfony/framework-bundle", "laravel/fortify",
                              "laravel/wayfinder") if f in req]
    scripts = composer.get("scripts", {}) if isinstance(composer.get("scripts"), dict) else {}
    commands = {k: f"composer {k}" for k in scripts
                if not k.startswith(("pre-", "post-")) and not k.startswith("@")}
    if os.path.isfile(os.path.join(root, "artisan")):
        commands.setdefault("serve", "php artisan serve")
        commands.setdefault("seed", "php artisan migrate:fresh --seed")
    return {"stack": "php", "name": composer.get("name"), "description": composer.get("description"),
            "php": req.get("php"), "frameworks": frameworks, "commands": commands}


def go_stack(root: str) -> dict | None:
    text = read(os.path.join(root, "go.mod"))
    if not text:
        return None
    module = re.search(r"^module\s+(\S+)", text, re.M)
    version = re.search(r"^go\s+(\S+)", text, re.M)
    mains = sorted({os.path.dirname(p) or "." for p in walk(root)
                    if p.endswith(".go") and "package main" in read(os.path.join(root, p))[:2000]})
    return {"stack": "go", "module": module.group(1) if module else None,
            "go": version.group(1) if version else None, "mains": mains,
            "commands": {"build": "go build ./...", "test": "go test ./...", "vet": "go vet ./..."}}


def python_stack(root: str) -> dict | None:
    text = read(os.path.join(root, "pyproject.toml"))
    has_setup = os.path.isfile(os.path.join(root, "setup.py"))
    if not text and not has_setup:
        return None
    name = re.search(r'^name\s*=\s*"([^"]+)"', text, re.M)
    scripts = re.search(r"^\[project\.scripts\]\n(.*?)(?=^\[|\Z)", text, re.M | re.S)
    return {"stack": "python", "name": name.group(1) if name else None,
            "scripts": re.findall(r"^([\w-]+)\s*=", scripts.group(1), re.M) if scripts else [],
            "commands": {"test": "pytest" if "pytest" in text else "python3 -m unittest"}}


def rust_stack(root: str) -> dict | None:
    text = read(os.path.join(root, "Cargo.toml"))
    if not text:
        return None
    name = re.search(r'^name\s*=\s*"([^"]+)"', text, re.M)
    return {"stack": "rust", "name": name.group(1) if name else None,
            "commands": {"build": "cargo build", "test": "cargo test", "run": "cargo run"}}


def godot_stack(root: str) -> dict | None:
    text = read(os.path.join(root, "project.godot"))
    if not text:
        return None
    name = re.search(r'^config/name="([^"]+)"', text, re.M)
    return {"stack": "godot", "name": name.group(1) if name else None, "commands": {}}


def claude_plugins_stack(root: str) -> dict | None:
    """A Claude Code plugin, or a marketplace of them: its commands are its skills."""
    market = load_json(os.path.join(root, ".claude-plugin", "marketplace.json"))
    single = load_json(os.path.join(root, ".claude-plugin", "plugin.json"))
    if not market and not single:
        return None
    entries = market.get("plugins", []) if market else [{"name": single.get("name"), "source": "."}]
    plugins = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("source"), str):
            continue
        base = os.path.normpath(os.path.join(root, entry["source"]))
        manifest = load_json(os.path.join(base, ".claude-plugin", "plugin.json"))

        def listing(sub: str, suffix: str = "") -> list[str]:
            folder = os.path.join(base, sub)
            if not os.path.isdir(folder):
                return []
            return sorted(n[: -len(suffix)] if suffix else n for n in os.listdir(folder)
                          if (n.endswith(suffix) if suffix else
                              os.path.isfile(os.path.join(folder, n, "SKILL.md"))))

        name = entry.get("name") or manifest.get("name")
        plugins.append({
            "name": name,
            "source": os.path.relpath(base, root),
            "version": manifest.get("version"),
            "description": entry.get("description") or manifest.get("description"),
            "commands": [f"/{name}:{s}" for s in listing("skills")]
                        + [f"/{name}:{c}" for c in listing("commands", ".md")],
            "agents": listing("agents", ".md"),
            "hooks": os.path.isfile(os.path.join(base, "hooks", "hooks.json")),
        })
    commands = {}
    if os.path.isfile(os.path.join(root, "scripts", "check.sh")):
        commands["test"] = "./scripts/check.sh"
    return {"stack": "claude-plugins", "name": (market or single).get("name"),
            "description": (market or single).get("description"), "plugins": plugins,
            "commands": commands}


STACKS = (php_stack, node_stack, go_stack, python_stack, rust_stack, godot_stack,
          claude_plugins_stack)


# --------------------------------------------------------------------------
# Everything else
# --------------------------------------------------------------------------

def workflows(root: str, slug: str | None) -> list[dict]:
    out = []
    wf_dir = os.path.join(root, ".github", "workflows")
    if not os.path.isdir(wf_dir):
        return out
    for name in sorted(os.listdir(wf_dir)):
        if not name.endswith((".yml", ".yaml")):
            continue
        text = read(os.path.join(wf_dir, name))
        title = re.search(r"^name:\s*['\"]?(.+?)['\"]?\s*$", text, re.M)
        on_pr = bool(re.search(r"^\s*(pull_request|push)\b", text, re.M))
        code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
        releases = bool(re.search(r"^\s+tags:|^\s+release:|gh release|action-gh-release|"
                                  r"create-release|electron-builder|goreleaser", code, re.M))
        entry = {"file": name, "name": title.group(1) if title else name, "runs_on_push_or_pr": on_pr,
                 "releases": releases}
        if slug:
            base = f"https://github.com/{slug}/actions/workflows/{name}"
            entry["badge"] = f"[![{entry['name']}]({base}/badge.svg)]({base})"
        out.append(entry)
    return out


def licence(root: str) -> dict | None:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "COPYING"):
        text = read(os.path.join(root, name))
        if text:
            for spdx, pattern in LICENCES:
                if re.search(pattern, text, re.I):
                    return {"file": name, "spdx": spdx}
            return {"file": name, "spdx": None}
    return None


def existing_docs(root: str, files: list[str]) -> dict:
    readme = next((f for f in ("README.md", "readme.md", "Readme.md") if f in files), None)
    text = read(os.path.join(root, readme)) if readme else ""
    manual_dir = next((d for d in ("docs/manual", "docs/guide", "docs/user-guide", "docs")
                       if any(f.startswith(d + "/") and f.endswith(".md") for f in files)), None)
    chapters = sorted(f for f in files if manual_dir and f.startswith(manual_dir + "/")
                      and f.endswith(".md") and f.count("/") == manual_dir.count("/") + 1)
    return {
        "readme": readme,
        "readme_lines": text.count("\n"),
        "readme_headings": re.findall(r"^#{2,3} (.+)$", text, re.M),
        "readme_mermaid": text.count("```mermaid"),
        "readme_images": len(re.findall(r"!\[[^\]]*\]\(|<img\s", text)),
        "manual_dir": manual_dir,
        "manual_pages": chapters,
        "screenshot_plan": next((f for f in ("docs/screenshots.json", ".github/screenshots.json")
                                 if f in files), None),
        "other": sorted(f for f in files if f in ("CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md",
                                                   "AGENTS.md", "CLAUDE.md", "CODE_OF_CONDUCT.md")),
    }


def images(files: list[str]) -> dict:
    found: dict[str, list[str]] = {}
    for f in files:
        if f.lower().endswith(IMAGE_EXT) and not f.startswith(("public/", "resources/", "src/",
                                                               "assets/", "static/")):
            found.setdefault(os.path.dirname(f) or ".", []).append(os.path.basename(f))
    return found


def visual(root: str, files: list[str], stacks: list[dict]) -> dict:
    """What there is to take a picture of: a web UI, a desktop app, a CLI, a game."""
    kinds = []
    frameworks = {f for s in stacks for f in s.get("frameworks", [])}
    if os.path.isfile(os.path.join(root, "artisan")) or frameworks & {
            "react", "vue", "svelte", "next", "nuxt", "vite", "@inertiajs/react"} or any(
            f in ("index.html", "public/index.html") for f in files):
        kinds.append("web")
    if frameworks & {"electron", "nativephp/electron", "nativephp/desktop"}:
        kinds.append("desktop")
    if any(s.get("bin") or s.get("scripts") or s.get("mains") for s in stacks) or any(
            f.startswith(("cmd/", "bin/")) for f in files):
        kinds.append("cli")
    if any(s["stack"] == "godot" for s in stacks):
        kinds.append("game")
    if any(s["stack"] == "claude-plugins" for s in stacks):
        kinds.append("terminal")  # skills run in Claude Code; their scripts run in a shell
    seeders = sorted(f for f in files if re.search(r"(^|/)(seeders?|fixtures|demo)(/|$)", f, re.I)
                     and not f.startswith(("tests/", "test/")))[:20]
    browser_tests = sorted({f.split("/")[0] + "/" + f.split("/")[1] for f in files
                            if re.match(r"tests?/(Browser|e2e|E2E|playwright)/", f)})
    return {"kinds": kinds, "seeders": seeders, "browser_tests": browser_tests,
            "playwright": bool(frameworks & {"playwright", "@playwright/test", "playwright-core"})}


def survey(root: str) -> dict:
    root = os.path.abspath(root)
    files = list(walk(root))
    remote = git(root, "remote", "get-url", "origin")
    slug = github_slug(remote)
    stacks = [s for s in (fn(root) for fn in STACKS) if s]
    name = os.path.basename(root)
    return {
        "root": root,
        "name": name,
        "remote": remote or None,
        "github": slug,
        "default_branch": (git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
                           .split("/", 1)[-1] or None),
        "description": next((s.get("description") for s in stacks if s.get("description")), None),
        "stacks": stacks,
        "workflows": workflows(root, slug),
        "licence": licence(root),
        "docs": existing_docs(root, files),
        "images": images(files),
        "visual": visual(root, files, stacks),
        "top_level": sorted({f.split(os.sep)[0] for f in files}),
        "file_count": len(files),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=".", help="the repository to survey (default: .)")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.root):
        print(f"survey: not a directory: {args.root}", file=sys.stderr)
        return 1
    json.dump(survey(args.root), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
