#!/usr/bin/env python3
"""Opt-in checks of post-review.py against real GitHub. Read-only; posts nothing.

The unit suite stubs `gh`, so it proves the logic and nothing about whether
that logic matches what GitHub actually returns. These run the real `gh`
commands and assert the shapes the script depends on: that `pr view --json`
carries the fields it reads, that `pr diff` parses into anchorable lines, and
that the review and comment listings look the way the supersede path expects.

Nothing here writes. There is no POST, PATCH, PUT or DELETE, and the review
payload is only ever built and printed, never sent.

Skipped unless you point it at a pull request:

    FOUR_PASS_REVIEW_IT_PR=142 \\
    FOUR_PASS_REVIEW_IT_REPO=owner/repo \\
    python3 tests/test_post_review_integration.py

`gh` must be on PATH and authenticated. The PR can be any open one you can
read, including in a repository you do not own.

Not part of `scripts/check.sh`: it needs network and credentials, so CI would
be flaky and a fresh clone could not run it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTER = os.path.join(REPO, "skills", "review", "scripts", "post-review.py")
spec = importlib.util.spec_from_file_location("post_review", POSTER)
pr = importlib.util.module_from_spec(spec)
sys.modules["post_review"] = pr
spec.loader.exec_module(pr)  # type: ignore[union-attr]

PR = os.environ.get("FOUR_PASS_REVIEW_IT_PR")
REPO_SLUG = os.environ.get("FOUR_PASS_REVIEW_IT_REPO")


def gh_authenticated() -> bool:
    if not shutil.which("gh"):
        return False
    return subprocess.run(["gh", "auth", "status"],
                          capture_output=True).returncode == 0


REASON = ("set FOUR_PASS_REVIEW_IT_PR (and optionally FOUR_PASS_REVIEW_IT_REPO) "
          "with an authenticated `gh` to run the integration checks")


@unittest.skipUnless(PR and gh_authenticated(), REASON)
class AgainstRealGitHub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner_repo, cls.head_sha, cls.url = pr.pr_info(PR, REPO_SLUG)
        cls.diff = pr.pr_diff(PR, REPO_SLUG)

    def test_pr_info_returns_the_fields_the_script_reads(self):
        self.assertRegex(self.owner_repo, r"^[^/]+/[^/]+$")
        self.assertRegex(self.head_sha, r"^[0-9a-f]{7,40}$")
        self.assertTrue(self.url.startswith("http"))

    def test_the_real_diff_parses_into_anchorable_lines(self):
        files = pr.parse_diff(self.diff)
        self.assertTrue(files, "no files parsed out of a real PR diff")
        anchorable = sum(len(fl.right) for fl in files.values())
        self.assertGreater(anchorable, 0, "no head-side lines were anchorable")
        for path, fl in files.items():
            self.assertFalse(path.startswith(("a/", "b/", '"')),
                             f"path left unnormalised: {path!r}")
            for start, end in fl.hunks:
                self.assertLessEqual(start, end, f"inverted hunk in {path}")

    def test_a_finding_on_a_real_changed_line_anchors_inline(self):
        files = pr.parse_diff(self.diff)
        path, fl = next((p, f) for p, f in files.items() if f.right)
        finding = {"id": "COR-1", "title": "integration probe", "path": path,
                   "line": min(fl.right), "body": "not posted", "fix": "none"}
        payload, unanchored = pr.build_review([finding], "**Verdict:** PASS\n",
                                              files, self.head_sha)
        self.assertEqual(unanchored, [], "a line from the real diff did not anchor")
        self.assertEqual(payload["comments"][0]["path"], path)

    def test_review_listing_has_the_fields_the_supersede_path_uses(self):
        reviews = pr.gh_json("api", "--paginate",
                             f"repos/{self.owner_repo}/pulls/{PR}/reviews")
        self.assertIsInstance(reviews, list)
        for r in reviews[:5]:
            self.assertIn("id", r)
            self.assertIn("user", r)
            self.assertIn("login", r.get("user") or {})

    def test_comment_listing_carries_the_review_id_we_filter_on(self):
        comments = pr.gh_json("api", "--paginate",
                              f"repos/{self.owner_repo}/pulls/{PR}/comments")
        self.assertIsInstance(comments, list)
        for c in comments[:5]:
            self.assertIn("id", c)
            # the key stale_comment_ids() groups by
            self.assertIn("pull_request_review_id", c)

    def test_current_login_resolves(self):
        # Superseding refuses to touch anything when this returns None, so an
        # authenticated run must resolve it or the feature silently no-ops.
        self.assertIsNotNone(pr.current_login())

    def test_dry_run_posts_nothing_and_exits_clean(self):
        import contextlib
        import io
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            findings = os.path.join(tmp, "findings.json")
            summary = os.path.join(tmp, "summary.md")
            files = pr.parse_diff(self.diff)
            path, fl = next((p, f) for p, f in files.items() if f.right)
            with open(findings, "w", encoding="utf-8") as fh:
                json.dump([{"id": "COR-1", "title": "integration probe",
                            "path": path, "line": min(fl.right),
                            "body": "not posted", "fix": "none"}], fh)
            with open(summary, "w", encoding="utf-8") as fh:
                fh.write("**Verdict:** PASS_WITH_NOTES\n")
            argv = ["--pr", PR, "--findings", findings, "--summary", summary,
                    "--dry-run"]
            if REPO_SLUG:
                argv += ["--repo", REPO_SLUG]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                code = pr.main(argv)
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["commit_id"], self.head_sha)
        self.assertEqual(payload["event"], "APPROVE")


if __name__ == "__main__":
    if not (PR and gh_authenticated()):
        print(f"skipped: {REASON}")
    unittest.main(verbosity=1)
