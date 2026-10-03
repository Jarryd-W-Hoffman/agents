#!/usr/bin/env python3
"""Checks on the eval suite itself. Free and deterministic; no model runs.

`build_prompts.py` strips `EVAL:` comment lines, where a fixture records what
the case measures. If that stops working, the prompt hands the analyst the
answer and the case measures nothing.

Run: python3 tests/test_evals.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVALS = os.path.join(REPO, "evals")

spec = importlib.util.spec_from_file_location("build_prompts", os.path.join(EVALS, "build_prompts.py"))
bp = importlib.util.module_from_spec(spec)
sys.modules["build_prompts"] = bp
spec.loader.exec_module(bp)  # type: ignore[union-attr]

GIVEAWAYS = ("EVAL:", "bait --", "name collision --")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def scan_of(case: str) -> dict:
    text = read(os.path.join(EVALS, case, "prompt.md"))
    return json.loads(re.search(r"```json\n(.*?)\n```", text, re.S).group(1))


class Stripping(unittest.TestCase):
    def test_no_generated_prompt_leaks_an_annotation(self):
        for case in bp.CASES:
            text = read(os.path.join(EVALS, case, "prompt.md"))
            for giveaway in GIVEAWAYS:
                self.assertNotIn(giveaway, text, f"{case}/prompt.md leaks {giveaway!r}")

    def test_fixtures_actually_carry_annotations(self):
        annotated = set()
        for root, _, names in os.walk(os.path.join(EVALS, "fixtures")):
            for n in names:
                if "EVAL:" in read(os.path.join(root, n)):
                    rel = os.path.relpath(root, os.path.join(EVALS, "fixtures"))
                    annotated.add(rel.split(os.sep)[0])
        self.assertGreaterEqual(len(annotated), 4, annotated)


class Prompts(unittest.TestCase):
    def test_prompts_are_in_step_with_the_fixtures(self):
        self.assertEqual(bp.main(["--check"]), 0, "run python3 evals/build_prompts.py")

    def test_every_case_has_a_prompt_a_grader_and_a_fixture(self):
        for case, fixture in bp.CASES.items():
            with self.subTest(case=case):
                self.assertTrue(os.path.exists(os.path.join(EVALS, case, "prompt.md")))
                self.assertTrue(os.path.exists(os.path.join(EVALS, case, "graders", "criteria.md")))
                for part in ("INTENT.md", "base", "head"):
                    self.assertTrue(os.path.exists(os.path.join(EVALS, "fixtures", fixture, part)))

    def test_no_orphan_case_directories(self):
        on_disk = {d for d in os.listdir(EVALS) if os.path.exists(os.path.join(EVALS, d, "prompt.md"))}
        self.assertEqual(on_disk, set(bp.CASES))

    def test_prompts_tell_the_skill_the_packet_is_resolved(self):
        for case in bp.CASES:
            self.assertIn("already resolved", read(os.path.join(EVALS, case, "prompt.md")), case)

    def test_only_the_control_has_nothing_to_analyse(self):
        for case in bp.CASES:
            self.assertEqual(scan_of(case)["analyse"], case != "nothing-to-map", case)

    def test_the_cases_measure_what_the_scan_cannot_see(self):
        # If the scan ever found these by itself, the case would stop
        # measuring the analyst and start measuring grep.
        refs = {r["path"] for s in scan_of("recall-route-job-schedule")["symbols"]
                for r in s["references"]}
        self.assertNotIn("routes/console.php", refs)
        self.assertNotIn("app/Console/Commands/RemindOverdueInvoices.php", refs)
        collision = {r["path"] for s in scan_of("precision-name-collision")["symbols"]
                     for r in s["references"]}
        self.assertIn("app/Jobs/RotateApiTokens.php", collision,
                      "the bait must reach the analyst, or the case tests nothing")


class Graders(unittest.TestCase):
    def grader(self, case: str) -> str:
        return read(os.path.join(EVALS, case, "graders", "criteria.md"))

    def test_frontmatter(self):
        for case in bp.CASES:
            text = self.grader(case)
            self.assertRegex(text, re.compile(r"^type:\s*llm\s*$", re.M), case)
            self.assertRegex(text, re.compile(r"^weight:\s*\d+\s*$", re.M), case)

    def test_precision_grader_fails_an_empty_response(self):
        self.assertIn("contains no\nimpact map at all", self.grader("precision-name-collision"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
