#!/usr/bin/env python3
"""Tests for scripts/plan.py and registry.json.

`Selection` is this plugin's eval suite. Selection is path patterns, not a
model, so "did it pick the right plugins, and skip the right ones" is a
table of change shapes with exact answers, and it costs nothing to run.

Run: python3 tests/test_plan.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "plan", os.path.join(REPO, "scripts", "plan.py"))
plan_mod = importlib.util.module_from_spec(spec)
sys.modules["plan"] = plan_mod
spec.loader.exec_module(plan_mod)  # type: ignore[union-attr]

REGISTRY = plan_mod.load_registry()


def selected(files):
    return {s["plugin"] for s in plan_mod.plan(files, REGISTRY)["selected"]}


def follow_ups(files):
    return {f["plugin"] for f in plan_mod.plan(files, REGISTRY)["follow_ups"]}


FOUR, MIG, IMPACT, REG = "fourpass", "migrations", "impact", "regressions"

# change shape -> (changed files, plugins that must be selected)
CASES = {
    "nothing changed": ([], set()),
    "docs only": (["README.md", "docs/deploy.md", "CHANGELOG.md"], set()),
    "assets and licence only": (["public/logo.svg", "LICENSE"], set()),
    "lockfile only": (["composer.lock"], set()),
    "application code": (["app/Services/InvoiceService.php"], {FOUR, REG, IMPACT}),
    "tests only": (["tests/Feature/InvoiceTest.php"], {FOUR, REG}),
    "nested tests only": (["packages/billing/tests/unit/test_total.py"], {FOUR, REG}),
    "laravel migration alone": (
        ["database/migrations/2026_10_01_000000_add_currency.php"], {FOUR, REG, MIG, IMPACT}),
    "migration with model and docs": (
        ["database/migrations/2026_10_01_000000_add_currency.php", "app/Models/Order.php",
         "README.md"], {FOUR, REG, MIG, IMPACT}),
    "laravel module migration": (
        ["Modules/Billing/Database/Migrations/2026_10_01_000000_x.php"], {FOUR, REG, MIG, IMPACT}),
    "rails migration": (["db/migrate/20261001000000_add_currency.rb"], {FOUR, REG, MIG, IMPACT}),
    "django migration": (["shop/migrations/0007_order_currency.py"], {FOUR, REG, MIG, IMPACT}),
    "django migrations package marker only": (["shop/migrations/__init__.py"], {FOUR, REG, IMPACT}),
    "alembic revision": (["alembic/versions/3f2a_add_currency.py"], {FOUR, REG, MIG, IMPACT}),
    "flyway script": (["src/main/resources/db/migration/V12__add_currency.sql"], {FOUR, REG, MIG, IMPACT}),
    "prisma migration": (["prisma/migrations/20261001000000_x/migration.sql"], {FOUR, REG, MIG, IMPACT}),
    "config only": (["config/queue.php", ".env.example"], {FOUR, REG, IMPACT}),
    "ci workflow only": ([".github/workflows/deploy.yml"], {FOUR, REG, IMPACT}),
    "a file merely named like migrations": (["docs/migrations.md"], set()),
    "seeder is not a migration": (["database/seeders/UserSeeder.php"], {FOUR, REG, IMPACT}),
}


class Selection(unittest.TestCase):
    """Did it pick the right plugins, and skip the right ones?"""

    def test_every_case(self):
        for name, (files, want) in CASES.items():
            with self.subTest(case=name):
                self.assertEqual(selected(files), want)

    def test_cases_exercise_every_selectable_plugin_both_ways(self):
        # A plugin no case selects, or no case skips, is untested in that direction.
        for p in REGISTRY["plugins"]:
            if p["kind"] == "follow-up":
                continue
            picked = [n for n, (_, want) in CASES.items() if p["name"] in want]
            left = [n for n, (_, want) in CASES.items() if p["name"] not in want]
            self.assertTrue(picked, f"no case selects {p['name']}")
            self.assertTrue(left, f"no case skips {p['name']}")

    def test_skipped_plugins_say_why(self):
        result = plan_mod.plan(["README.md"], REGISTRY)
        reasons = {s["plugin"]: s["reason"] for s in result["skipped"]}
        self.assertIn("excluded", reasons[FOUR])
        self.assertIn("*.md", reasons[FOUR])
        self.assertEqual(reasons[MIG], "no changed file is the kind it reviews")
        self.assertEqual(plan_mod.plan([], REGISTRY)["skipped"][0]["reason"], "no changed files")

    def test_selected_plugins_carry_their_evidence(self):
        files = ["database/migrations/2026_10_01_000000_a.php", "README.md"]
        mig = next(s for s in plan_mod.plan(files, REGISTRY)["selected"] if s["plugin"] == MIG)
        self.assertEqual((mig["matched"], mig["evidence"]),
                         (1, ["database/migrations/2026_10_01_000000_a.php"]))

    def test_evidence_is_capped(self):
        files = [f"app/F{i}.php" for i in range(plan_mod.EVIDENCE_CAP + 3)]
        four = next(s for s in plan_mod.plan(files, REGISTRY)["selected"] if s["plugin"] == FOUR)
        self.assertEqual(four["matched"], plan_mod.EVIDENCE_CAP + 3)
        self.assertEqual(len(four["evidence"]), plan_mod.EVIDENCE_CAP)


class FollowUps(unittest.TestCase):
    def test_test_gap_writer_is_offered_after_four_pass_only(self):
        self.assertEqual(follow_ups(["app/X.php"]), {"testgaps"})
        self.assertEqual(follow_ups(["README.md"]), set())

    def test_follow_ups_are_never_selected(self):
        self.assertNotIn("testgaps", selected(["app/X.php", "tests/XTest.php"]))


class Globs(unittest.TestCase):
    def test_semantics(self):
        cases = [
            ("*.md", "README.md", True), ("*.md", "docs/a/b.md", True),
            ("docs/**", "docs/a/b.md", True), ("docs/**", "src/docs/a.md", False),
            ("**/migrations/**", "database/migrations/x.php", True),
            ("**/migrations/**", "migrations/x.sql", True),
            ("**/migrations/**", "docs/migrations.md", False),
            ("db/migrate/**", "db/migrate/1_x.rb", True),
            ("db/migrate/**", "api/db/migrate/1_x.rb", False),
            ("*Test.php", "tests/Unit/FooTest.php", True), ("*Test.php", "src/Testing.php", False),
            ("**", "anything/at/all", True), ("LICENSE*", "LICENSE.txt", True),
            ("a?c", "abc", True), ("a?c", "a/c", False),
        ]
        for pattern, path, want in cases:
            with self.subTest(pattern=pattern, path=path):
                self.assertEqual(bool(plan_mod.glob_regex(pattern).match(path)), want)


class Registry(unittest.TestCase):
    def test_is_valid(self):
        self.assertEqual(plan_mod.validate_registry(REGISTRY), [])

    def test_validation_catches_mistakes(self):
        broken = json.loads(json.dumps(REGISTRY))
        broken["plugins"][0]["kind"] = "reviewer"
        broken["plugins"][1]["skill"] = "check"
        broken["plugins"][2]["include"] = []
        broken["plugins"][3]["after"] = ["nope"]
        broken["plugins"][1]["prefixes"] = ["COR"]
        errors = "\n".join(plan_mod.validate_registry(broken))
        for fragment in ("kind must be one of", "must be namespaced", "can never be selected",
                         "unknown plugin 'nope'", "prefix 'COR' is claimed by more than one"):
            self.assertIn(fragment, errors)

    def test_prefixes_match_the_finding_contract_table(self):
        # The finding contract's README lists every prefix in use; the
        # registry must agree with it on the ones it claims.
        prefixes = {p["name"]: set(p["prefixes"]) for p in REGISTRY["plugins"]}
        self.assertEqual(prefixes[FOUR], {"CMP", "COR", "CPL", "CNS"})
        self.assertEqual(prefixes[MIG], {"MIG"})


class Cli(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = plan_mod.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_files_mode(self):
        code, out, _ = self.run_main(["--files", "database/migrations/2026_10_01_000000_a.php"])
        self.assertEqual(code, 0)
        self.assertIn(MIG, {s["plugin"] for s in json.loads(out)["selected"]})

    def test_invalid_registry_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "registry.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"version": 2, "plugins": []}, fh)
            code, out, err = self.run_main(["--files", "a.php", "--registry", path])
        self.assertEqual((code, out), (1, ""))
        self.assertIn("version must be 1", err)

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_against_a_real_repository_including_untracked(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)

        def g(*a):
            subprocess.run(["git", "-C", tmp, *a], check=True, capture_output=True)
        g("init", "-q")
        g("config", "user.email", "t@example.com")
        g("config", "user.name", "t")
        with open(os.path.join(tmp, "README.md"), "w") as fh:
            fh.write("x\n")
        g("add", ".")
        g("commit", "-q", "-m", "init")
        os.makedirs(os.path.join(tmp, "database", "migrations"))
        with open(os.path.join(tmp, "database", "migrations", "2026_10_01_000000_a.php"), "w") as fh:
            fh.write("<?php\n")
        cwd = os.getcwd()
        os.chdir(tmp)
        self.addCleanup(os.chdir, cwd)
        code, out, err = self.run_main(["--base", "HEAD"])
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertEqual(data["head"], "working tree")
        self.assertEqual({s["plugin"] for s in data["selected"]}, {FOUR, REG, MIG, IMPACT})

    def test_not_a_repository_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                code, _, err = self.run_main(["--base", "HEAD"])
            finally:
                os.chdir(cwd)
        self.assertEqual(code, 1)
        self.assertIn("plan:", err)


if __name__ == "__main__":
    unittest.main(verbosity=1)
