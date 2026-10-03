#!/usr/bin/env python3
"""Tests for skills/check/scripts/find-migrations.py. Run: python3 tests/test_find_migrations.py"""

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
SCRIPT = os.path.join(REPO, "skills", "check", "scripts", "find-migrations.py")
spec = importlib.util.spec_from_file_location("find_migrations", SCRIPT)
fm = importlib.util.module_from_spec(spec)
sys.modules["find_migrations"] = fm
spec.loader.exec_module(fm)  # type: ignore[union-attr]

BASE_FILES = """\
app/Models/User.php
config/database.php
.env.example
CLAUDE.md
.claude/rules/database.md
deploy.php
database/schema/mysql-schema.sql
database/migrations/2026_01_10_000000_create_users_table.php
database/migrations/2026_03_02_120000_create_orders_table.php
database/migrations/2026_05_01_000000_add_status_to_orders.php
""".splitlines()


class FrameworkOf(unittest.TestCase):
    CASES = {
        "database/migrations/2026_10_01_000000_add_x.php": "laravel",
        "Modules/Billing/Database/Migrations/2026_10_01_000000_x.php": "laravel",
        "db/migrate/20261001000000_add_x.rb": "rails",
        "shop/migrations/0007_order_status.py": "django",
        "alembic/versions/3f2a_add_x.py": "alembic",
        "migrations/versions/3f2a_add_x.py": "alembic",
        "src/main/resources/db/migration/V12__add_x.sql": "flyway",
        "prisma/migrations/20261001000000_add_x/migration.sql": "prisma",
        "migrations/004_add_x.sql": "sql",
        "migrations/20261001_add_x.ts": "node",
    }

    def test_known_layouts(self):
        for path, want in self.CASES.items():
            self.assertEqual(fm.framework_of(path), want, path)

    def test_not_migrations(self):
        for path in ("app/Models/Order.php", "shop/migrations/__init__.py",
                     "database/seeders/UserSeeder.php", "database/factories/UserFactory.php",
                     "tests/Feature/MigrationTest.php", "docs/migrations.md"):
            self.assertIsNone(fm.framework_of(path), path)


class Classify(unittest.TestCase):
    def run_classify(self, name_status, untracked=None):
        return fm.classify(name_status, BASE_FILES, untracked)

    def test_no_migrations(self):
        r = self.run_classify("M\tapp/Models/User.php\nA\tapp/Http/Controllers/X.php\n")
        self.assertEqual(r["migrations"], [])
        self.assertEqual(r["frameworks"], [])

    def test_added_migration(self):
        r = self.run_classify("A\tdatabase/migrations/2026_10_01_000000_drop_email.php\n")
        (m,) = r["migrations"]
        self.assertEqual((m["status"], m["framework"]), ("added", "laravel"))
        self.assertNotIn("out_of_order", m)
        self.assertEqual(r["frameworks"], ["laravel"])

    def test_statuses_of_existing_migrations(self):
        r = self.run_classify(
            "M\tdatabase/migrations/2026_03_02_120000_create_orders_table.php\n"
            "D\tdatabase/migrations/2026_01_10_000000_create_users_table.php\n")
        self.assertEqual([m["status"] for m in r["migrations"]], ["modified", "deleted"])

    def test_rename_keeps_the_old_path(self):
        r = self.run_classify("R087\tdatabase/migrations/2026_05_01_000000_add_status_to_orders.php\t"
                              "database/migrations/2026_05_01_000000_add_state_to_orders.php\n")
        (m,) = r["migrations"]
        self.assertEqual(m["status"], "renamed")
        self.assertEqual(m["old_path"], "database/migrations/2026_05_01_000000_add_status_to_orders.php")
        self.assertEqual(m["path"], "database/migrations/2026_05_01_000000_add_state_to_orders.php")

    def test_out_of_order_added_migration(self):
        # Dated before a migration that already exists, e.g. a long-lived branch.
        r = self.run_classify("A\tdatabase/migrations/2026_04_01_000000_add_index.php\n")
        self.assertTrue(r["migrations"][0]["out_of_order"])

    def test_out_of_order_is_per_directory(self):
        r = self.run_classify("A\tModules/Billing/Database/Migrations/2026_02_01_000000_x.php\n")
        self.assertNotIn("out_of_order", r["migrations"][0])

    def test_untracked_files_count_as_added(self):
        r = self.run_classify("", ["database/migrations/2026_10_02_000000_new.php", "notes.txt"])
        self.assertEqual([(m["path"], m["status"]) for m in r["migrations"]],
                         [("database/migrations/2026_10_02_000000_new.php", "added")])

    def test_context_files_come_from_base(self):
        r = self.run_classify("")
        self.assertEqual(r["schema_files"], ["database/schema/mysql-schema.sql"])
        self.assertEqual(r["deploy_files"], [".env.example", "config/database.php", "deploy.php"])
        self.assertEqual(r["rule_files"], [".claude/rules/database.md", "CLAUDE.md"])

    def test_rails_and_flyway_versions(self):
        base = ["db/migrate/20260501000000_a.rb", "db/migration/V2_1__b.sql"]
        r = fm.classify("A\tdb/migrate/20260401000000_c.rb\nA\tdb/migration/V2__d.sql\n"
                        "A\tdb/migration/V10__e.sql\n", base)
        flags = {m["path"]: m.get("out_of_order", False) for m in r["migrations"]}
        self.assertEqual(flags, {"db/migrate/20260401000000_c.rb": True,
                                 "db/migration/V2__d.sql": True,
                                 "db/migration/V10__e.sql": False})


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = fm.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_offline_mode(self):
        ns = self.write("ns", "A\tdatabase/migrations/2026_10_01_000000_x.php\n")
        bf = self.write("bf", "\n".join(BASE_FILES))
        code, out, _ = self.run_main(["--name-status", ns, "--base-files", bf])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["migrations"][0]["framework"], "laravel")

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_against_a_real_repository(self):
        def g(*a):
            subprocess.run(["git", "-C", self.tmp, *a], check=True, capture_output=True)
        g("init", "-q")
        g("config", "user.email", "t@example.com")
        g("config", "user.name", "t")
        os.makedirs(os.path.join(self.tmp, "database", "migrations"))
        self.write("database/migrations/2026_01_01_000000_create_users.php", "<?php\n")
        g("add", ".")
        g("commit", "-q", "-m", "init")
        self.write("database/migrations/2026_01_01_000000_create_users.php", "<?php // edited\n")
        self.write("database/migrations/2026_10_01_000000_untracked.php", "<?php\n")
        cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, cwd)
        code, out, err = self.run_main(["--base", "HEAD"])
        self.assertEqual(code, 0, err)
        got = {m["path"]: m["status"] for m in json.loads(out)["migrations"]}
        self.assertEqual(got, {"database/migrations/2026_01_01_000000_create_users.php": "modified",
                               "database/migrations/2026_10_01_000000_untracked.php": "added"})

    def test_git_failure_exits_1(self):
        cwd = os.getcwd()
        os.chdir(self.tmp)  # not a repository
        self.addCleanup(os.chdir, cwd)
        code, out, err = self.run_main(["--base", "HEAD"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("find-migrations:", err)


if __name__ == "__main__":
    unittest.main(verbosity=1)
