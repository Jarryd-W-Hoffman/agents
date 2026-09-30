#!/usr/bin/env python3
"""Tests for skills/review/scripts/post-review.py. Run: python3 tests/test_post_review.py"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTER = os.path.join(REPO, "skills", "review", "scripts", "post-review.py")
spec = importlib.util.spec_from_file_location("post_review", POSTER)
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

# A hunk whose content lines start with "-- " / "++ " and so look like file headers.
SQL_DIFF = """diff --git a/db/query.sql b/db/query.sql
index 3333333..4444444 100644
--- a/db/query.sql
+++ b/db/query.sql
@@ -1,3 +1,3 @@
 SELECT 1;
--- SQL comment
+++ x
 SELECT 2;
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

    def test_header_lookalikes_inside_hunk_are_content(self):
        files = pr.parse_diff(SQL_DIFF)
        self.assertEqual(list(files), ["db/query.sql"])  # "+++ x" must not open a file "x"
        fl = files["db/query.sql"]
        self.assertEqual(fl.left, {1, 2, 3})   # old 2 is the deleted "-- SQL comment"
        self.assertEqual(fl.right, {1, 2, 3})  # new 2 is the added "++ x"
        self.assertEqual(fl.hunks, [(1, 3)])


class QuotedPaths(unittest.TestCase):
    """Git quotes non-ASCII paths; unquoted, they never match a finding."""

    UNICODE_DIFF = (
        'diff --git "a/caf\\303\\251.py" "b/caf\\303\\251.py"\n'
        'index 111..222 100644\n'
        '--- "a/caf\\303\\251.py"\n'
        '+++ "b/caf\\303\\251.py"\n'
        '@@ -1 +1 @@\n'
        '-x\n'
        '+y\n'
    )

    def test_octal_escaped_utf8_path_is_decoded(self):
        files = pr.parse_diff(self.UNICODE_DIFF)
        self.assertEqual(list(files), ["café.py"])

    def test_a_finding_on_that_file_anchors_inline(self):
        files = pr.parse_diff(self.UNICODE_DIFF)
        f = {"id": "COR-1", "title": "t", "path": "café.py", "line": 1}
        payload, unanchored = pr.build_review([f], "s", files, "abc")
        self.assertEqual(unanchored, [])
        self.assertEqual(payload["comments"][0]["path"], "café.py")

    def test_c_escapes_and_plain_paths(self):
        self.assertEqual(pr._unquote_diff_path('"b/a\\tb.py"'), "b/a\tb.py")
        self.assertEqual(pr._unquote_diff_path('"b/say \\"hi\\".py"'), 'b/say "hi".py')
        self.assertEqual(pr._unquote_diff_path("b/plain.py"), "b/plain.py")
        self.assertEqual(pr._unquote_diff_path('"'), '"')

    def test_unquoted_path_with_spaces_is_untouched(self):
        diff = ("diff --git a/my dir/f.py b/my dir/f.py\n"
                "--- a/my dir/f.py\n+++ b/my dir/f.py\n@@ -1 +1 @@\n-x\n+y\n")
        self.assertEqual(list(pr.parse_diff(diff)), ["my dir/f.py"])


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

    def test_head_line_outside_hunks_is_not_anchored_left(self):
        # head line 41 is in no hunk; old line 41 exists but is an unrelated base line
        f = self.finding(id="CMP-1", line=41)
        payload, un = pr.build_review([f], self.summary, self.files, "abc")
        self.assertEqual(payload["comments"], [])
        self.assertEqual([u["id"] for u in un], ["CMP-1"])
        self.assertIn("`app/Exporter.php:41`", payload["body"])

    def test_explicit_left_side_anchors_deleted_line(self):
        # old line 12 is the deleted "$email = $invoice->customer->email;"
        f = self.finding(id="CMP-1", line=12, side="LEFT")
        payload, un = pr.build_review([f], self.summary, self.files, "abc")
        self.assertEqual(un, [])
        c = payload["comments"][0]
        self.assertEqual((c["path"], c["side"], c["line"]), ("app/Exporter.php", "LEFT", 12))
        self.assertNotIn("start_line", c)

    def test_explicit_left_side_unknown_line_is_unanchored(self):
        f = self.finding(id="CMP-1", line=99, side="LEFT")
        payload, un = pr.build_review([f], self.summary, self.files, "abc")
        self.assertEqual(payload["comments"], [])
        self.assertEqual([u["id"] for u in un], ["CMP-1"])

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


class BodyBullets(unittest.TestCase):
    """Every body-only rendering path must produce the same bullet for the same finding."""

    def setUp(self):
        self.files = pr.parse_diff(DIFF)
        self.summary = "# Four-pass review: PR #1\n\n**Verdict:** FAIL\n"
        self.finding = {"id": "CNS-1", "title": "Naming drift", "severity": "minor",
                        "pass": "consistency", "path": "app/Exporter.php", "line": 99,
                        "body": "Sibling uses camelCase.", "fix": "Rename to fooBar."}
        self.bullet = pr._body_bullet(self.finding)

    def test_bullet_shape(self):
        self.assertEqual(self.bullet,
                         "- **[CNS-1]** `app/Exporter.php:99` — Naming drift (minor · consistency)\n"
                         "  - Fix: Rename to fooBar.")

    def test_bullet_without_optional_fields(self):
        self.assertEqual(pr._body_bullet({"id": "X-1", "title": "t", "path": "./a.py", "line": 3}),
                         "- **[X-1]** `a.py:3` — t")

    def test_unanchored_section_uses_bullet(self):
        payload, _ = pr.build_review([self.finding], self.summary, self.files, "abc")
        self.assertIn(f"### {pr.UNANCHORED_HEADING}\n\n{self.bullet}\n", payload["body"])

    def test_summary_body_uses_bullet(self):
        body = pr.build_summary_body([self.finding], self.summary)
        self.assertTrue(body.startswith(self.summary.rstrip() + "\n"))
        self.assertIn(f"### {pr.SUMMARY_HEADING}\n\n{self.bullet}\n", body)
        self.assertTrue(body.endswith(f"\n{pr.FOOTER}\n"))

    def test_summary_body_validates_required_fields(self):
        with self.assertRaises(ValueError):
            pr.build_summary_body([{"id": "X", "title": "t", "path": "a"}], self.summary)

    def test_fallback_body_uses_bullet(self):
        # The 422 fallback passes an empty diff map so every finding lands in the body.
        anchorable = {"id": "COR-1", "title": "Null customer", "path": "app/Exporter.php", "line": 13}
        payload, un = pr.build_review([anchorable, self.finding], self.summary, {}, "abc",
                                      heading=pr.FALLBACK_HEADING)
        self.assertEqual(payload["comments"], [])
        self.assertEqual([u["id"] for u in un], ["COR-1", "CNS-1"])
        self.assertIn(f"### {pr.FALLBACK_HEADING}\n\n", payload["body"])
        self.assertIn(pr._body_bullet(anchorable) + "\n" + self.bullet + "\n", payload["body"])
        self.assertNotIn(pr.UNANCHORED_HEADING, payload["body"])

    def test_main_is_importable(self):
        self.assertTrue(callable(pr.main))


class VerdictEvents(unittest.TestCase):
    def test_verdict_read_from_summary_header(self):
        for verdict in ("PASS", "PASS_WITH_NOTES", "REQUEST_CHANGES", "FAIL"):
            with self.subTest(verdict=verdict):
                body = f"# Four-pass review: PR #1\n\n**Verdict:** {verdict}\n**Scope:** 1 file\n"
                self.assertEqual(pr.verdict_from_summary(body), verdict)

    def test_unknown_or_missing_verdict_is_none(self):
        self.assertIsNone(pr.verdict_from_summary("# Report\n\nno verdict line\n"))
        self.assertIsNone(pr.verdict_from_summary("**Verdict:** MAYBE\n"))

    def test_event_for_each_verdict(self):
        self.assertEqual(pr.event_for_verdict("PASS"), "APPROVE")
        self.assertEqual(pr.event_for_verdict("PASS_WITH_NOTES"), "APPROVE")
        self.assertEqual(pr.event_for_verdict("REQUEST_CHANGES"), "REQUEST_CHANGES")
        self.assertEqual(pr.event_for_verdict("FAIL"), "REQUEST_CHANGES")

    def test_unknown_verdict_falls_back_to_comment(self):
        self.assertEqual(pr.event_for_verdict(None), "COMMENT")
        self.assertEqual(pr.event_for_verdict("MAYBE"), "COMMENT")

    def test_build_review_carries_the_event(self):
        files = pr.parse_diff(DIFF)
        summary = "**Verdict:** FAIL\n"
        payload, _ = pr.build_review([], summary, files, "abc", event="REQUEST_CHANGES")
        self.assertEqual(payload["event"], "REQUEST_CHANGES")

    def test_build_review_defaults_to_comment(self):
        files = pr.parse_diff(DIFF)
        payload, _ = pr.build_review([], "**Verdict:** PASS_WITH_NOTES\n", files, "abc")
        self.assertEqual(payload["event"], "COMMENT")

    def test_incomplete_never_approves(self):
        # A pass that crashed has not said "nothing wrong". If this ever maps
        # to APPROVE, a broken reviewer can approve a pull request.
        self.assertEqual(pr.event_for_verdict("INCOMPLETE"), "COMMENT")

    def test_incomplete_is_read_off_a_qualified_header(self):
        summary = "**Verdict:** INCOMPLETE — compliance did not report\n"
        self.assertEqual(pr.verdict_from_summary(summary), "INCOMPLETE")
        self.assertEqual(pr.event_for_verdict(pr.verdict_from_summary(summary)),
                         "COMMENT")

    def test_only_pass_verdicts_approve(self):
        approving = {v for v, e in pr.VERDICT_EVENTS.items() if e == "APPROVE"}
        self.assertEqual(approving, {"PASS", "PASS_WITH_NOTES"})

    def test_only_blocking_verdicts_request_changes(self):
        blocking = {v for v, e in pr.VERDICT_EVENTS.items() if e == "REQUEST_CHANGES"}
        self.assertEqual(blocking, {"REQUEST_CHANGES", "FAIL"})


class Suggestions(unittest.TestCase):
    """A ```suggestion block is only honoured on a head-side inline comment."""

    def finding(self, **kw):
        f = {"id": "COR-1", "title": "t", "path": "app/Exporter.php", "line": 13,
             "suggestion": "$email = $customer?->email;"}
        f.update(kw)
        return f

    def test_right_side_anchor_gets_the_block(self):
        files = pr.parse_diff(DIFF)
        payload, _ = pr.build_review([self.finding()], "s", files, "abc")
        body = payload["comments"][0]["body"]
        self.assertIn("```suggestion\n$email = $customer?->email;\n```", body)

    def test_left_side_anchor_does_not(self):
        # old line 12 is the deleted "$email = $invoice->customer->email;"
        files = pr.parse_diff(DIFF)
        f = self.finding(line=12, side="LEFT")
        payload, unanchored = pr.build_review([f], "s", files, "abc")
        self.assertEqual(unanchored, [])
        self.assertEqual(payload["comments"][0]["side"], "LEFT")
        self.assertNotIn("```suggestion", payload["comments"][0]["body"])

    def test_unanchored_finding_does_not(self):
        files = pr.parse_diff(DIFF)
        f = self.finding(path="app/Exporter.php", line=9999)
        payload, unanchored = pr.build_review([f], "s", files, "abc")
        self.assertEqual(len(unanchored), 1)
        self.assertNotIn("```suggestion", payload["body"])

    def test_absent_suggestion_renders_nothing(self):
        files = pr.parse_diff(DIFF)
        f = self.finding()
        del f["suggestion"]
        payload, _ = pr.build_review([f], "s", files, "abc")
        self.assertNotIn("```suggestion", payload["comments"][0]["body"])

    def test_empty_suggestion_is_still_rendered(self):
        # An empty replacement is how a finding says "delete these lines".
        files = pr.parse_diff(DIFF)
        payload, _ = pr.build_review([self.finding(suggestion="")], "s", files, "abc")
        self.assertIn("```suggestion\n\n```", payload["comments"][0]["body"])


class ReviewedMarker(unittest.TestCase):
    """The footer records the reviewed head, so a re-review knows what it covered."""

    def test_footer_carries_the_sha_and_still_contains_the_marker(self):
        line = pr.footer_line("abc123def456")
        self.assertIn(pr.FOOTER, line)          # prior-review matching unchanged
        self.assertIn("reviewed at abc123def456", line)

    def test_footer_without_a_sha_is_the_bare_marker(self):
        self.assertEqual(pr.footer_line(), pr.FOOTER)

    def test_build_review_stamps_the_commit(self):
        payload, _ = pr.build_review([], "s", {}, "deadbeef1234")
        self.assertIn("reviewed at deadbeef1234", payload["body"])

    def test_summary_body_stamps_the_commit(self):
        body = pr.build_summary_body([], "s", "deadbeef1234")
        self.assertIn("reviewed at deadbeef1234", body)

    def test_last_reviewed_sha_reads_the_newest(self):
        reviews = [
            {"id": 1, "body": f"old\n\n{pr.footer_line('1111111')}",
             "user": {"login": "me"}},
            {"id": 2, "body": f"new\n\n{pr.footer_line('2222222')}",
             "user": {"login": "me"}},
        ]
        self.assertEqual(pr.last_reviewed_sha(reviews, "me"), "2222222")

    def test_a_superseded_review_still_answers_what_it_covered(self):
        # supersede() keeps the marker; otherwise every re-review starts over.
        reviews = [{"id": 1, "user": {"login": "me"},
                    "body": f"{pr.SUPERSEDED_NOTE}\n\n{pr.footer_line('3333333')}"}]
        self.assertEqual(pr.last_reviewed_sha(reviews, "me"), "3333333")
        # ...but it is not a candidate for superseding again
        self.assertEqual(pr.find_prior_reviews(reviews, "me"), [])

    def test_no_prior_review_means_no_sha(self):
        self.assertIsNone(pr.last_reviewed_sha([], "me"))
        self.assertIsNone(pr.last_reviewed_sha(
            [{"id": 1, "body": "unrelated", "user": {"login": "me"}}], "me"))

    def test_another_accounts_review_is_not_consulted(self):
        reviews = [{"id": 1, "user": {"login": "someone-else"},
                    "body": f"x\n\n{pr.footer_line('4444444')}"}]
        self.assertIsNone(pr.last_reviewed_sha(reviews, "me"))


class PriorRuns(unittest.TestCase):
    """Re-reviewing must not leave the PR with duplicate reviews and comments."""

    def review(self, rid, body, login="me"):
        return {"id": rid, "body": body, "user": {"login": login}}

    def test_finds_our_review_by_footer(self):
        reviews = [
            self.review(1, "someone else's review"),
            self.review(2, f"report\n\n{pr.FOOTER}\n"),
        ]
        self.assertEqual([r["id"] for r in pr.find_prior_reviews(reviews, "me")], [2])

    def test_ignores_another_users_review(self):
        reviews = [self.review(3, f"report\n\n{pr.FOOTER}\n", login="someone-else")]
        self.assertEqual(pr.find_prior_reviews(reviews, "me"), [])

    def test_ignores_an_already_superseded_review(self):
        reviews = [self.review(4, f"{pr.SUPERSEDED_NOTE}\n\n{pr.FOOTER}")]
        self.assertEqual(pr.find_prior_reviews(reviews, "me"), [])

    def test_footer_alone_is_not_enough_to_supersede(self):
        # Superseding deletes inline comments, which cannot be undone. A review
        # is only a candidate when we can prove whose it is, so an account we
        # are not signed in as is never matched on the footer alone.
        reviews = [self.review(5, f"report\n\n{pr.FOOTER}\n", login="whoever")]
        self.assertEqual(pr.find_prior_reviews(reviews, "me"), [])

    def test_comment_of_another_account_is_not_matched(self):
        comments = [{"id": 9, "body": f"x\n{pr.FOOTER}", "user": {"login": "someone-else"}}]
        self.assertIsNone(pr.find_prior_comment(comments, "me"))

    def test_prior_comment_is_the_most_recent(self):
        comments = [
            {"id": 1, "body": f"old\n{pr.FOOTER}", "user": {"login": "me"}},
            {"id": 2, "body": "unrelated", "user": {"login": "me"}},
            {"id": 3, "body": f"new\n{pr.FOOTER}", "user": {"login": "me"}},
        ]
        self.assertEqual(pr.find_prior_comment(comments, "me")["id"], 3)

    def test_no_prior_comment(self):
        self.assertIsNone(pr.find_prior_comment([{"id": 1, "body": "x",
                                                  "user": {"login": "me"}}], "me"))

    def test_stale_comment_ids_are_scoped_to_our_reviews(self):
        comments = [
            {"id": 10, "pull_request_review_id": 2},
            {"id": 11, "pull_request_review_id": 99},
            {"id": 12, "pull_request_review_id": 2},
        ]
        self.assertEqual(pr.stale_comment_ids(comments, {2}), [10, 12])


class OfflineDryRun(unittest.TestCase):
    """--dry-run with a saved diff must not touch the network."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.diff = os.path.join(self.tmp, "pr.diff")
        with open(self.diff, "w", encoding="utf-8") as fh:
            fh.write(DIFF)
        self.findings = os.path.join(self.tmp, "findings.json")
        with open(self.findings, "w", encoding="utf-8") as fh:
            json.dump([{"id": "COR-1", "title": "t", "path": "app/Exporter.php",
                        "line": 13, "body": "b", "fix": "f"}], fh)
        self.summary = os.path.join(self.tmp, "summary.md")
        with open(self.summary, "w", encoding="utf-8") as fh:
            fh.write("**Verdict:** FAIL\n")
        self.real_gh = pr.gh
        pr.gh = self.explode
        self.addCleanup(setattr, pr, "gh", self.real_gh)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def explode(self, *a, **kw):
        raise AssertionError(f"offline dry run called gh: {a}")

    def run_main(self, *extra):
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            code = pr.main(["--pr", "1", "--findings", self.findings,
                            "--summary", self.summary, "--dry-run",
                            "--diff-file", self.diff, "--head-sha", "abc123",
                            *extra])
        return code, buf.getvalue()

    def test_inline_dry_run_is_offline(self):
        code, out = self.run_main()
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["event"], "REQUEST_CHANGES")
        self.assertEqual(payload["comments"][0]["path"], "app/Exporter.php")

    def test_summary_dry_run_is_offline(self):
        code, out = self.run_main("--mode", "summary")
        self.assertEqual(code, 0)
        self.assertIn(pr.FOOTER, out)


class GhStub:
    """Records `gh` calls and replays canned answers, so the I/O paths are testable."""

    def __init__(self, answers=None, fail=()):
        self.calls = []
        self.answers = answers or {}
        self.fail = set(fail)

    def __call__(self, *args, input_text=None):
        self.calls.append(args)
        key = " ".join(args)
        for pattern in self.fail:
            if pattern in key:
                raise RuntimeError(f"gh failed: {pattern}")
        for pattern, answer in self.answers.items():
            if pattern in key:
                return answer
        return "{}"

    def methods(self):
        """(method, path) for each `gh api --method X path` call."""
        out = []
        for a in self.calls:
            if a[:1] == ("api",) and "--method" in a:
                i = a.index("--method")
                out.append((a[i + 1], a[i + 2]))
        return out


class Supersede(unittest.TestCase):
    """Superseding deletes comments, so its failure modes matter more than most."""

    def setUp(self):
        self.real_gh, self.real_gh_json = pr.gh, pr.gh_json
        self.addCleanup(setattr, pr, "gh", self.real_gh)
        self.addCleanup(setattr, pr, "gh_json", self.real_gh_json)

    def install(self, comments, **kw):
        stub = GhStub(**kw)
        pr.gh = stub
        pr.gh_json = lambda *a: comments
        return stub

    def test_deletes_only_our_comments_then_blanks_the_review(self):
        comments = [
            {"id": 10, "pull_request_review_id": 7},
            {"id": 11, "pull_request_review_id": 999},   # someone else's review
        ]
        stub = self.install(comments)
        pr.supersede_reviews("o/r", "1", [{"id": 7}])
        self.assertEqual(stub.methods(), [
            ("DELETE", "repos/o/r/pulls/comments/10"),
            ("PUT", "repos/o/r/pulls/1/reviews/7"),
        ])

    def test_a_failed_delete_does_not_stop_the_rest(self):
        comments = [{"id": 10, "pull_request_review_id": 7}]
        stub = self.install(comments, fail=["pulls/comments/10"])
        with contextlib.redirect_stderr(io.StringIO()) as err:
            pr.supersede_reviews("o/r", "1", [{"id": 7}])
        # the review body is still blanked even though the delete failed
        self.assertIn(("PUT", "repos/o/r/pulls/1/reviews/7"), stub.methods())
        self.assertIn("could not delete stale comment 10", err.getvalue())

    def test_a_failed_put_is_reported_not_raised(self):
        stub = self.install([], fail=["reviews/7"])
        with contextlib.redirect_stderr(io.StringIO()) as err:
            pr.supersede_reviews("o/r", "1", [{"id": 7}])   # must not raise
        self.assertIn("could not supersede review 7", err.getvalue())

    def test_nothing_to_supersede_touches_nothing(self):
        stub = self.install([])
        pr.supersede_reviews("o/r", "1", [])
        self.assertEqual(stub.calls, [])


class PostFallbacks(unittest.TestCase):
    """The degrade path: GitHub refusing the event, or refusing an anchor."""

    def setUp(self):
        self.real = pr.post_review
        self.addCleanup(setattr, pr, "post_review", self.real)

    def payload(self, event="APPROVE"):
        return {"commit_id": "abc", "event": event, "body": "b",
                "comments": [{"path": "p", "line": 1, "body": "x"}]}

    def test_self_review_falls_back_to_comment(self):
        seen = []

        def fake(owner_repo, prnum, payload):
            seen.append(payload["event"])
            if payload["event"] != "COMMENT":
                raise RuntimeError("422 Can not approve your own pull request")
            return {"html_url": "u"}

        pr.post_review = fake
        with contextlib.redirect_stderr(io.StringIO()) as err:
            out = pr.post_review_with_fallbacks("o/r", "1", self.payload(), [], "s", "abc")
        self.assertEqual(out, {"html_url": "u"})
        self.assertEqual(seen, ["APPROVE", "COMMENT"])
        self.assertIn("your own PR", err.getvalue())

    def test_rejected_anchor_retries_body_only_keeping_the_event(self):
        seen = []

        def fake(owner_repo, prnum, payload):
            seen.append((payload["event"], len(payload["comments"])))
            if payload["comments"]:
                raise RuntimeError("422 Unprocessable Entity: line must be part of the diff")
            return {"html_url": "u"}

        pr.post_review = fake
        findings = [{"id": "COR-1", "title": "t", "path": "p", "line": 1}]
        with contextlib.redirect_stderr(io.StringIO()):
            out = pr.post_review_with_fallbacks("o/r", "1", self.payload("REQUEST_CHANGES"),
                                                findings, "s", "abc")
        self.assertEqual(out, {"html_url": "u"})
        # same event, second attempt carries no inline comments
        self.assertEqual(seen, [("REQUEST_CHANGES", 1), ("REQUEST_CHANGES", 0)])

    def test_an_unrelated_error_is_raised(self):
        def fake(*a):
            raise RuntimeError("404 Not Found")

        pr.post_review = fake
        with self.assertRaises(RuntimeError):
            pr.post_review_with_fallbacks("o/r", "1", self.payload(), [], "s", "abc")


if __name__ == "__main__":
    unittest.main(verbosity=1)
