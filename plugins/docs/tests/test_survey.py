#!/usr/bin/env python3
"""Tests for scripts/survey.py, against small repositories built on the fly.

Run: python3 tests/test_survey.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("survey", os.path.join(REPO, "scripts", "survey.py"))
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)

MIT = "MIT License\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\n"


def build(files: dict) -> str:
    root = tempfile.mkdtemp()
    for rel, content in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content if isinstance(content, str) else json.dumps(content))
    return root


class Laravel(unittest.TestCase):
    def setUp(self):
        self.root = build({
            "artisan": "#!/usr/bin/env php\n",
            "composer.json": {"name": "acme/jobs", "description": "Jobs for surveyors.",
                              "require": {"php": "^8.5", "laravel/framework": "^13.0",
                                          "inertiajs/inertia-laravel": "^3.0"},
                              "require-dev": {"pestphp/pest": "^4.0"},
                              "scripts": {"test": "pest", "dev": "...", "post-install-cmd": "x"}},
            "package.json": {"devDependencies": {"react": "^19", "vite": "^7"},
                             "scripts": {"build": "vite build", "dev": "vite"}},
            "package-lock.json": "{}",
            "database/seeders/DatabaseSeeder.php": "<?php\n",
            "tests/Browser/LoginTest.php": "<?php\n",
            ".github/workflows/tests.yml": "name: Tests\non:\n  push:\n  pull_request:\n",
            ".github/screenshots/hero.png": "png",
            "LICENSE": MIT,
            "README.md": "# Jobs\n\n## Features\n\n```mermaid\nflowchart LR\n```\n",
            "docs/manual/README.md": "# Manual\n",
            "docs/manual/01-getting-started.md": "# Getting started\n",
            "docs/manual/images/x.png": "png",
            "node_modules/react/index.js": "",
            "vendor/laravel/x.php": "",
        })
        subprocess.run(["git", "init", "-q", self.root], check=True)
        subprocess.run(["git", "-C", self.root, "remote", "add", "origin",
                        "git@github.com:acme/jobs.git"], check=True)
        self.data = survey.survey(self.root)

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_identity(self):
        self.assertEqual(self.data["github"], "acme/jobs")
        self.assertEqual(self.data["description"], "Jobs for surveyors.")
        self.assertEqual(self.data["licence"], {"file": "LICENSE", "spdx": "MIT"})

    def test_stacks_and_commands(self):
        php, node = self.data["stacks"]
        self.assertEqual(php["stack"], "php")
        self.assertIn("laravel/framework", php["frameworks"])
        self.assertEqual(php["commands"]["test"], "composer test")
        self.assertNotIn("post-install-cmd", php["commands"])
        self.assertEqual(php["commands"]["serve"], "php artisan serve")
        self.assertEqual(node["manager"], "npm")
        self.assertEqual(node["commands"]["build"], "npm run build")

    def test_badge_for_each_workflow(self):
        (wf,) = self.data["workflows"]
        self.assertEqual(wf["name"], "Tests")
        self.assertIn("https://github.com/acme/jobs/actions/workflows/tests.yml/badge.svg", wf["badge"])

    def test_docs_and_images(self):
        docs = self.data["docs"]
        self.assertEqual(docs["readme"], "README.md")
        self.assertEqual(docs["readme_mermaid"], 1)
        self.assertEqual(docs["manual_dir"], "docs/manual")
        self.assertEqual(docs["manual_pages"], ["docs/manual/01-getting-started.md",
                                                "docs/manual/README.md"])
        self.assertEqual(self.data["images"][".github/screenshots"], ["hero.png"])

    def test_something_to_screenshot(self):
        visual = self.data["visual"]
        self.assertIn("web", visual["kinds"])
        self.assertEqual(visual["seeders"], ["database/seeders/DatabaseSeeder.php"])
        self.assertEqual(visual["browser_tests"], ["tests/Browser"])

    def test_dependency_dirs_are_skipped(self):
        self.assertNotIn("node_modules", self.data["top_level"])
        self.assertNotIn("vendor", self.data["top_level"])


class GoCli(unittest.TestCase):
    def test_a_go_cli(self):
        root = build({"go.mod": "module github.com/acme/rill\n\ngo 1.26\n",
                      "cmd/rill/main.go": "package main\n\nfunc main() {}\n",
                      "vm/vm.go": "package vm\n"})
        try:
            data = survey.survey(root)
        finally:
            shutil.rmtree(root)
        (go,) = data["stacks"]
        self.assertEqual(go["mains"], ["cmd/rill"])
        self.assertEqual(go["commands"]["test"], "go test ./...")
        self.assertEqual(data["visual"]["kinds"], ["cli"])
        self.assertIsNone(data["github"])
        self.assertIsNone(data["licence"])


class Remotes(unittest.TestCase):
    def test_github_slug(self):
        for remote in ("git@github.com:a/b.git", "https://github.com/a/b", "https://github.com/a/b.git/"):
            self.assertEqual(survey.github_slug(remote), "a/b", remote)
        self.assertIsNone(survey.github_slug("git@gitlab.com:a/b.git"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
