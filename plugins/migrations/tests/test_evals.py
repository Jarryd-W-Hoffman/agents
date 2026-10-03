#!/usr/bin/env python3
"""Checks on the eval suite itself. Free and deterministic; no model runs.

The one that matters most: `build_prompts.py` strips `EVAL:` comment lines,
which is where a fixture records the defect it seeds. If that stops working,
the prompt hands the reviewer the answer and every recall case passes while
measuring nothing.

Run: python3 tests/test_evals.py
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVALS = os.path.join(REPO, "evals")

spec = importlib.util.spec_from_file_location(
    "build_prompts", os.path.join(EVALS, "build_prompts.py"))
bp = importlib.util.module_from_spec(spec)
sys.modules["build_prompts"] = bp
spec.loader.exec_module(bp)  # type: ignore[union-attr]

GIVEAWAYS = ("EVAL:", "seeded defect", "bait --")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Stripping(unittest.TestCase):
    def test_no_generated_prompt_leaks_an_annotation(self):
        for case in bp.CASES:
            text = read(os.path.join(EVALS, case, "prompt.md"))
            for giveaway in GIVEAWAYS:
                self.assertNotIn(giveaway, text,
                                 f"{case}/prompt.md hands the reviewer the answer; "
                                 "run python3 evals/build_prompts.py")

    def test_fixtures_actually_carry_annotations(self):
        # Otherwise the test above passes vacuously.
        annotated = set()
        for root, _, names in os.walk(os.path.join(EVALS, "fixtures")):
            for n in names:
                if "EVAL:" in read(os.path.join(root, n)):
                    annotated.add(os.path.relpath(root, os.path.join(EVALS, "fixtures")).split(os.sep)[0])
        self.assertGreaterEqual(len(annotated), 6, annotated)


class Prompts(unittest.TestCase):
    def test_prompts_are_in_step_with_the_fixtures(self):
        self.assertEqual(bp.main(["--check"]), 0, "run python3 evals/build_prompts.py")

    def test_every_case_has_a_prompt_a_grader_and_a_fixture(self):
        for case, fixture in bp.CASES.items():
            with self.subTest(case=case):
                self.assertTrue(os.path.exists(os.path.join(EVALS, case, "prompt.md")))
                self.assertTrue(os.path.exists(os.path.join(EVALS, case, "graders", "criteria.md")))
                for part in ("INTENT.md", "base", "head"):
                    self.assertTrue(os.path.exists(os.path.join(EVALS, "fixtures", fixture, part)),
                                    f"{fixture}/{part}")

    def test_no_orphan_case_directories(self):
        on_disk = {d for d in os.listdir(EVALS)
                   if os.path.exists(os.path.join(EVALS, d, "prompt.md"))}
        self.assertEqual(on_disk, set(bp.CASES))

    def test_prompts_tell_the_skill_the_packet_is_resolved(self):
        for case in bp.CASES:
            self.assertIn("already resolved", read(os.path.join(EVALS, case, "prompt.md")), case)

    def test_migration_cases_list_migrations_and_the_control_lists_none(self):
        # The packet comes from the real detector. If it stopped recognising a
        # fixture's migration, a recall case would silently become a
        # no-migrations case and fail for the wrong reason.
        for case, fixture in bp.CASES.items():
            text = read(os.path.join(EVALS, case, "prompt.md"))
            empty = '"migrations": []' in text
            with self.subTest(case=case):
                self.assertEqual(empty, case == "no-migrations")

    def test_edited_migration_is_reported_as_modified(self):
        text = read(os.path.join(EVALS, "recall-edited-migration", "prompt.md"))
        self.assertRegex(text, r'"status": "modified",\s*"framework": "laravel"')


class Graders(unittest.TestCase):
    def grader(self, case: str) -> str:
        return read(os.path.join(EVALS, case, "graders", "criteria.md"))

    def test_frontmatter(self):
        for case in bp.CASES:
            text = self.grader(case)
            self.assertRegex(text, re.compile(r"^type:\s*llm\s*$", re.M), case)
            self.assertRegex(text, re.compile(r"^weight:\s*\d+\s*$", re.M), case)

    def test_recall_graders_require_a_mig_finding_at_blocking_severity(self):
        for case in bp.CASES:
            if case.startswith("recall-"):
                text = self.grader(case)
                self.assertIn("`MIG-`", text, case)
                self.assertIn("critical or major", text, case)

    def test_precision_graders_score_the_false_positive_not_the_verdict(self):
        for case in bp.CASES:
            if case.startswith("precision-"):
                text = self.grader(case)
                self.assertIn("Score 0 if any such finding appears", text, case)
                self.assertIn("Minor findings and Notes are irrelevant", text, case)

    def test_precision_graders_fail_a_run_that_produced_no_report(self):
        # Measured: a run refused before it started scored 1.00 on a precision
        # case, because an empty response contains no false positive.
        for case in bp.CASES:
            if case.startswith("precision-"):
                self.assertIn("contains no migration safety report at all",
                              self.grader(case), case)


if __name__ == "__main__":
    unittest.main(verbosity=1)
