#!/usr/bin/env python3
"""Tests for skills/hunt/scripts/history-scan.py and evals/repo_builder.py.

Every test that needs history builds a real git repository; git is the thing
being driven, so faking it would test nothing.

Run: python3 tests/test_history_scan.py
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
sys.path.insert(0, os.path.join(REPO, "evals"))
import repo_builder  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "history_scan", os.path.join(REPO, "skills", "hunt", "scripts", "history-scan.py"))
hs = importlib.util.module_from_spec(spec)
sys.modules["history_scan"] = hs
spec.loader.exec_module(hs)  # type: ignore[union-attr]

FIXTURES = os.path.join(REPO, "evals", "fixtures")
HAVE_GIT = shutil.which("git") is not None


def strip(text: str) -> str:
    out = "\n".join(ln for ln in text.splitlines() if "EVAL:" not in ln)
    return out + ("\n" if text.endswith("\n") else "")


class InRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def build(self, fixture: str) -> list[str]:
        shas = repo_builder.build(os.path.join(FIXTURES, fixture), self.tmp, strip=strip)
        os.chdir(self.tmp)
        return shas

    def scan(self, base="HEAD", head=None):
        return hs.scan(base, head)


class Classify(unittest.TestCase):
    def test_fix_revert_and_refs(self):
        self.assertEqual(hs.classify("Fix double charge (#311)", ""), (["fix"], None, ["#311"]))
        kinds, reverted, refs = hs.classify('Revert "Use tags"', "This reverts commit abc1234.\n\nINC-142.")
        self.assertEqual((kinds, reverted, refs), (["revert"], "abc1234", ["INC-142"]))

    def test_plain_feature_is_neither(self):
        for subject in ("Add the customer name to the PDF", "Show totals on the dashboard",
                        "Prefix routes", "Refactor the recorder"):
            self.assertEqual(hs.classify(subject, "")[0], [], subject)

    def test_fix_words_need_word_boundaries(self):
        self.assertEqual(hs.classify("Add prefix to cache keys", "")[0], [])
        self.assertEqual(hs.classify("Hotfix: guard null customer", "")[0], ["fix"])


class Hunks(unittest.TestCase):
    def test_ranges_at_base(self):
        diff = ("--- a/x.php\n+++ b/x.php\n@@ -10,3 +10,2 @@\n-a\n-b\n-c\n+d\n+e\n"
                "@@ -20,0 +20,2 @@\n+f\n+g\n")
        got = hs.hunks(diff)["x.php"]
        self.assertEqual(got["ranges"], [(10, 12), (19, 22)])

    def test_rename_and_new_file(self):
        diff = "--- a/old.php\n+++ b/new.php\n@@ -1 +1 @@\n-a\n+b\n--- /dev/null\n+++ b/added.php\n@@ -0,0 +1 @@\n+x\n"
        got = hs.hunks(diff)
        self.assertEqual(got["new.php"]["base_path"], "old.php")
        self.assertIsNone(got["added.php"]["base_path"])


class Reviewable(unittest.TestCase):
    def test_categories(self):
        for path in ("app/X.php", "tests/Feature/XTest.php", "config/cache.php", ".env.example"):
            self.assertTrue(hs.reviewable(path), path)
        for path in ("README.md", "docs/a.php", "composer.lock", "public/logo.svg", "LICENSE"):
            self.assertFalse(hs.reviewable(path), path)


@unittest.skipUnless(HAVE_GIT, "git not installed")
class Builder(InRepo):
    def test_same_fixture_same_shas(self):
        first = self.build("fix-guard-removed")
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other, True)
        second = repo_builder.build(os.path.join(FIXTURES, "fix-guard-removed"), other, strip=strip)
        self.assertEqual(first, second)

    def test_sha_placeholder_resolves(self):
        shas = self.build("revert-reintroduced")
        body = subprocess.run(["git", "log", "-1", "--format=%b", shas[2]], capture_output=True,
                              text=True, check=True).stdout
        self.assertIn(f"This reverts commit {shas[1]}.", body)

    def test_annotations_never_reach_history_or_tree(self):
        self.build("fix-guard-removed")
        log = subprocess.run(["git", "log", "-p", "--all"], capture_output=True, text=True, check=True).stdout
        self.assertNotIn("EVAL:", log)
        tree = subprocess.run(["git", "grep", "-n", "EVAL:"], capture_output=True, text=True).stdout
        self.assertEqual(tree, "")


@unittest.skipUnless(HAVE_GIT, "git not installed")
class Fixtures(InRepo):
    def test_revert_reintroduced(self):
        shas = self.build("revert-reintroduced")
        r = self.scan()
        self.assertTrue(r["analyse"])
        (f,) = r["files"]
        top = f["commits"][0]
        self.assertEqual((top["sha"], top["kinds"], top["on_changed_lines"]), (shas[2], ["revert"], True))
        self.assertEqual((top["reverts"], top["refs"]), (shas[1], ["INC-142"]))

    def test_fix_guard_removed_surfaces_the_fix(self):
        shas = self.build("fix-guard-removed")
        r = self.scan()
        top = r["files"][0]["commits"][0]
        self.assertEqual((top["sha"], top["kinds"], top["refs"], top["on_changed_lines"]),
                         (shas[2], ["fix"], ["#311"], True))

    def test_guard_kept_has_the_same_signal(self):
        # Precision is the agent's job: the history alone cannot tell the two
        # webhook changes apart, and must not pretend to.
        shas = self.build("fix-guard-kept")
        self.assertEqual(self.scan()["files"][0]["commits"][0]["sha"], shas[2])

    def test_quiet_history_stops(self):
        self.build("quiet-history")
        r = self.scan()
        self.assertFalse(r["analyse"])
        self.assertIn("no fix or revert touched the changed lines", r["reason"])

    def test_commit_range_target(self):
        self.build("quiet-history")
        r = self.scan(base="HEAD~1", head="HEAD")
        self.assertEqual([f["path"] for f in r["files"]], ["app/Pdf/InvoicePdf.php"])


@unittest.skipUnless(HAVE_GIT, "git not installed")
class CoChange(InRepo):
    def commit(self, files: dict[str, str], message: str):
        for rel, text in files.items():
            path = os.path.join(self.tmp, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(text)
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t")
        subprocess.run(["git", "-c", "commit.gpgsign=false", "add", "-A"], cwd=self.tmp, check=True, env=env)
        subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", message], cwd=self.tmp,
                       check=True, env=env)

    def test_usual_partner_missing_is_reported(self):
        subprocess.run(["git", "init", "-q", self.tmp], check=True)
        os.chdir(self.tmp)
        for i in range(4):
            self.commit({"app/Enums/Status.php": f"case S{i};\n", "resources/lang/en/status.php": f"'s{i}',\n"},
                        f"Add status {i}")
        self.commit({"app/Other.php": "x\n"}, "Add other")
        with open("app/Enums/Status.php", "a") as fh:
            fh.write("case S9;\n")
        r = self.scan()
        (f,) = r["files"]
        self.assertEqual(f["missing_partners"], [{"path": "resources/lang/en/status.php", "together": 4, "of": 4}])
        self.assertTrue(r["analyse"])

    def test_partner_present_is_not_reported(self):
        subprocess.run(["git", "init", "-q", self.tmp], check=True)
        os.chdir(self.tmp)
        for i in range(4):
            self.commit({"a.php": f"{i}\n", "b.php": f"{i}\n"}, f"Change {i}")
        for rel in ("a.php", "b.php"):
            with open(rel, "a") as fh:
                fh.write("z\n")
        self.assertEqual(self.scan()["files"][0]["missing_partners"], [])


@unittest.skipUnless(HAVE_GIT, "git not installed")
class Cli(InRepo):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = hs.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_prints_json(self):
        self.build("fix-guard-removed")
        code, out, err = self.run_main(["--base", "HEAD"])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["head"], "working tree")

    def test_not_a_repository(self):
        os.chdir(self.tmp)
        code, _, err = self.run_main(["--base", "HEAD"])
        self.assertEqual(code, 1)
        self.assertIn("history-scan:", err)


if __name__ == "__main__":
    unittest.main(verbosity=1)
