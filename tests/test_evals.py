#!/usr/bin/env python3
"""Checks on the eval suite itself. Free and deterministic; no model runs.

The scored suite costs about $0.80 a run and is non-deterministic, so it is not
in CI. These are the parts that can be checked for nothing, and one of them
matters more than it looks:

`build_prompts.py` strips `EVAL:` comment lines, which are where a fixture
records the defect it seeds. If that ever stops working, the prompt hands the
reviewer the answer, every recall case passes, and the suite reports success
while measuring nothing at all. That is a failure that looks exactly like
success, so it gets a test.

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

# Words that only ever appear in a maintainer annotation. If one reaches a
# prompt, the reviewer is being told what to find.
GIVEAWAYS = ("EVAL:", "SEEDED DEFECT", "seeded defect", "bait --", "bait:")

PREFIX_FOR = {"correctness": "COR-", "completeness": "CMP-",
              "compliance": "CPL-", "consistency": "CNS-"}

# Compiled with the flags baked in: unittest's assertRegex takes a message as
# its third argument, not flags, so passing re.M there silently does nothing.
GRADER_TYPE_RE = re.compile(r"^type:\s*llm\s*$", re.M)
GRADER_WEIGHT_RE = re.compile(r"^weight:\s*\d+\s*$", re.M)
VERDICT_IRRELEVANT_RE = re.compile(
    r"do not consider the verdict|verdict (do|does) not matter|"
    r"verdict may be anything", re.I)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Stripping(unittest.TestCase):
    """The annotations must never reach a prompt."""

    def test_no_generated_prompt_leaks_an_annotation(self):
        for case in bp.CASES:
            text = read(os.path.join(EVALS, case, "prompt.md"))
            for giveaway in GIVEAWAYS:
                if giveaway not in text:
                    continue
                # Show the offending line, not the whole prompt.
                line = next(ln for ln in text.splitlines() if giveaway in ln)
                self.fail(
                    f"{case}/prompt.md leaks {giveaway!r}:\n"
                    f"    {line.strip()[:100]}\n"
                    "  the reviewer is being handed the answer, so the case "
                    "measures nothing. Run python3 evals/build_prompts.py.")

    def test_strip_annotations_removes_the_whole_line(self):
        src = "a = 1\n    # EVAL: seeded defect (correctness)\nb = 2\n"
        self.assertEqual(bp.strip_annotations(src), "a = 1\nb = 2")

    def test_strip_annotations_keeps_ordinary_comments(self):
        src = "# a real comment\nx = 1\n"
        self.assertEqual(bp.strip_annotations(src), "# a real comment\nx = 1")

    def test_fixtures_actually_carry_annotations(self):
        # If the fixtures stopped annotating, the stripping test above would
        # pass vacuously.
        annotated = []
        for root, _, names in os.walk(os.path.join(EVALS, "fixtures")):
            for n in names:
                if "EVAL:" in read(os.path.join(root, n)):
                    annotated.append(n)
        self.assertGreaterEqual(
            len(annotated), 4,
            "fixtures no longer record which defect they seed; the stripping "
            f"test is passing for the wrong reason (found: {annotated})")


class Prompts(unittest.TestCase):
    def test_prompts_are_in_step_with_the_fixtures(self):
        self.assertEqual(bp.main(["--check"]), 0,
                         "run python3 evals/build_prompts.py")

    def test_every_case_has_a_prompt_and_a_grader(self):
        for case in bp.CASES:
            with self.subTest(case=case):
                self.assertTrue(os.path.exists(os.path.join(EVALS, case, "prompt.md")))
                self.assertTrue(os.path.exists(
                    os.path.join(EVALS, case, "graders", "criteria.md")))

    def test_every_case_names_a_fixture_that_exists(self):
        for case, (fixture, _) in bp.CASES.items():
            with self.subTest(case=case):
                self.assertTrue(
                    os.path.isdir(os.path.join(EVALS, "fixtures", fixture)),
                    f"{case} points at missing fixture {fixture!r}")

    def test_no_orphan_case_directories(self):
        on_disk = {d for d in os.listdir(EVALS)
                   if os.path.isdir(os.path.join(EVALS, d))
                   and os.path.exists(os.path.join(EVALS, d, "prompt.md"))}
        self.assertEqual(on_disk, set(bp.CASES),
                         "a case directory exists that build_prompts.py does not "
                         "know about, so it is never regenerated")

    def test_prompts_tell_the_skill_the_packet_is_resolved(self):
        # Without this the lead spends its turn budget resolving a target
        # against a workspace that has no repository in it.
        for case in bp.CASES:
            text = read(os.path.join(EVALS, case, "prompt.md"))
            with self.subTest(case=case):
                self.assertIn("already resolved", text)


class Graders(unittest.TestCase):
    def grader(self, case: str) -> str:
        return read(os.path.join(EVALS, case, "graders", "criteria.md"))

    def test_recall_graders_require_the_owning_pass(self):
        # A finding reported by the wrong pass means the scope boundaries have
        # stopped holding, so the prefix is part of the assertion.
        for case in bp.CASES:
            if not case.startswith("recall-"):
                continue
            which = case.split("-", 1)[1]
            with self.subTest(case=case):
                self.assertIn(PREFIX_FOR[which], self.grader(case),
                              f"{case} does not require a {PREFIX_FOR[which]} finding")

    def test_precision_graders_do_not_score_on_the_verdict(self):
        # A clean fixture can legitimately draw a "no tests" finding. Scoring
        # the verdict measures that instead of the false positive.
        for case in bp.CASES:
            if not case.startswith("precision-"):
                continue
            text = self.grader(case)
            with self.subTest(case=case):
                self.assertRegex(
                    text, VERDICT_IRRELEVANT_RE,
                    f"{case} must say the verdict is irrelevant, or it measures "
                    "the wrong thing")

    def test_every_grader_declares_a_type_and_weight(self):
        for case in bp.CASES:
            text = self.grader(case)
            with self.subTest(case=case):
                self.assertRegex(text, GRADER_TYPE_RE)
                self.assertRegex(text, GRADER_WEIGHT_RE)


if __name__ == "__main__":
    unittest.main(verbosity=1)
