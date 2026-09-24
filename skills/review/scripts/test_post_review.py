#!/usr/bin/env python3
"""Tests for skills/review/scripts/post-review.py. Run: python3 skills/review/scripts/test_post_review.py"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("post_review", os.path.join(HERE, "post-review.py"))
pr = importlib.util.module_from_spec(spec)
sys.modules["post_review"] = pr
spec.loader.exec_module(pr)  # type: ignore[union-attr]

DIFF = """diff --git a/app/Exporter.php b/app/Exporter.php
index 1111111..2222222 100644
--- a/app/Exporter.php
+++ b/app/Exporter.php
@@ -10,6 +10,8 @@ class Exporter
     public function run(Invoice $invoice): string
     {
-        $email = $invoice->customer->email;
+        $customer = $invoice->customer;
+        $email = $customer->email;
+        $this->log($email);
         return $this->render($email);
     }
 }
@@ -40,3 +42,4 @@ class Exporter
     private function render(string $email): string
     {
+        // TODO
         return $email;
diff --git a/tests/ExporterTest.php b/tests/ExporterTest.php
new file mode 100644
--- /dev/null
+++ b/tests/ExporterTest.php
@@ -0,0 +1,3 @@
+<?php
+// test
+final class ExporterTest {}
diff --git a/old.txt b/old.txt
deleted file mode 100644
--- a/old.txt
+++ /dev/null
@@ -1,2 +0,0 @@
-gone
-gone too
\\ No newline at end of file
"""


class ParseDiff(unittest.TestCase):
    def setUp(self):
        self.files = pr.parse_diff(DIFF)

    def test_files_found(self):
        self.assertIn("app/Exporter.php", self.files)
        self.assertIn("tests/ExporterTest.php", self.files)
        self.assertNotIn("old.txt", self.files)  # deleted file has no head side

    def test_right_side_lines_first_hunk(self):
        fl = self.files["app/Exporter.php"]
        # new lines 10..17: context 10,11 ; added 12,13,14 ; context 15,16,17
        self.assertEqual(fl.right & set(range(10, 18)), set(range(10, 18)))
        self.assertIn(13, fl.right)  # "$email = $customer->email;"
        self.assertNotIn(18, fl.right)  # not part of any hunk

    def test_left_side_deleted_line(self):
        fl = self.files["app/Exporter.php"]
        self.assertIn(12, fl.left)  # the removed "$email = $invoice->customer->email;"

    def test_second_hunk(self):
        fl = self.files["app/Exporter.php"]
        self.assertIn(44, fl.right)  # "// TODO"
        self.assertEqual(fl.hunks, [(10, 17), (42, 45)])

    def test_new_file(self):
        fl = self.files["tests/ExporterTest.php"]
        self.assertEqual(fl.right, {1, 2, 3})
        self.assertEqual(fl.left, set())


class BuildReview(unittest.TestCase):
    def setUp(self):
        self.files = pr.parse_diff(DIFF)
        self.summary = "# Four-pass review: PR #1\n\n**Verdict:** FAIL\n"

    def finding(self, **kw):
        base = {"id": "COR-1", "title": "Null customer", "severity": "critical",
                "confidence": 92, "pass": "correctness", "path": "app/Exporter.php",
                "line": 13, "body": "customer_id is nullable.", "fix": "Guard it."}
        base.update(kw)
        return base

    def test_inline_anchor_right(self):
        payload, un = pr.build_review([self.finding()], self.summary, self.files, "abc")
        self.assertEqual(un, [])
        self.assertEqual(payload["event"], "COMMENT")
        self.assertEqual(payload["commit_id"], "abc")
        c = payload["comments"][0]
        self.assertEqual((c["path"], c["line"], c["side"]), ("app/Exporter.php", 13, "RIGHT"))
        self.assertIn("**[COR-1] Null customer**", c["body"])
        self.assertIn("critical · confidence 92 · correctness", c["body"])
        self.assertIn("**Suggested fix:** Guard it.", c["body"])
        self.assertIn(pr.FOOTER, payload["body"])

    def test_multiline_range_same_hunk(self):
        payload, _ = pr.build_review([self.finding(line=12, end_line=14)], self.summary, self.files, "abc")
        c = payload["comments"][0]
        self.assertEqual((c["start_line"], c["line"]), (12, 14))
        self.assertEqual(c["start_side"], "RIGHT")

    def test_multiline_range_across_hunks_falls_back_to_single_line(self):
        payload, _ = pr.build_review([self.finding(line=16, end_line=44)], self.summary, self.files, "abc")
        c = payload["comments"][0]
        self.assertNotIn("start_line", c)
        self.assertEqual(c["line"], 16)

    def test_left_side_anchor_for_deleted_line(self):
        f = self.finding(id="CMP-1", path="app/Exporter.php", line=12)
        # line 12 is both a RIGHT line (added) and a LEFT line (deleted); RIGHT wins
        payload, _ = pr.build_review([f], self.summary, self.files, "abc")
        self.assertEqual(payload["comments"][0]["side"], "RIGHT")

    def test_unanchorable_line_goes_to_body(self):
        f = self.finding(id="CNS-1", line=99, title="Naming drift")
        payload, un = pr.build_review([f], self.summary, self.files, "abc")
        self.assertEqual(payload["comments"], [])
        self.assertEqual([u["id"] for u in un], ["CNS-1"])
        self.assertIn("Findings outside the diff", payload["body"])
        self.assertIn("`app/Exporter.php:99` — Naming drift", payload["body"])
        self.assertIn("Fix: Guard it.", payload["body"])

    def test_unknown_file_goes_to_body(self):
        f = self.finding(id="CPL-1", path="./docs/policy.md", line=3)
        payload, un = pr.build_review([f], self.summary, self.files, "abc")
        self.assertEqual(len(un), 1)
        self.assertIn("`docs/policy.md:3`", payload["body"])

    def test_path_normalisation(self):
        f = self.finding(path="`./app/Exporter.php`")
        payload, un = pr.build_review([f], self.summary, self.files, "abc")
        self.assertEqual(un, [])
        self.assertEqual(payload["comments"][0]["path"], "app/Exporter.php")

    def test_missing_required_field(self):
        with self.assertRaises(ValueError):
            pr.build_review([{"id": "X", "title": "t", "path": "a"}], self.summary, self.files, "abc")

    def test_no_findings(self):
        payload, un = pr.build_review([], self.summary, self.files, "abc")
        self.assertEqual(payload["comments"], [])
        self.assertTrue(payload["body"].startswith("# Four-pass review"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
