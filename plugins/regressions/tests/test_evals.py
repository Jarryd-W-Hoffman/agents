#!/usr/bin/env python3
"""Checks on the eval suite itself. No model runs; needs git, which builds the fixtures.

`build_prompts.py` strips `EVAL:` lines, where a fixture records the seeded
regression or the bait, from both the repository it builds and the prompt.
If that stops working, the reviewer is handed the answer.

Run: python3 tests/test_evals.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVALS = os.path.join(REPO, "evals")

spec = importlib.util.spec_from_file_location("build_prompts", os.path.join(EVALS, "build_prompts.py"))
bp = importlib.util.module_from_spec(spec)
sys.modules["build_prompts"] = bp
spec.loader.exec_module(bp)  # type: ignore[union-attr]

GIVEAWAYS = ("EVAL:", "seeded regression", "bait --")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def scan_of(case: str) -> dict:
    text = read(os.path.join(EVALS, case, "prompt.md"))
    return json.loads(re.search(r"```json\n(.*?)\n```", text, re.S).group(1))


class Stripping(unittest.TestCase):
    def test_no_prompt_leaks_an_annotation(self):
        for case in bp.CASES:
            text = read(os.path.join(EVALS, case, "prompt.md"))
            for giveaway in GIVEAWAYS:
                self.assertNotIn(giveaway, text, f"{case} leaks {giveaway!r}")

    def test_fixtures_carry_annotations(self):
        annotated = set()
        for root, _, names in os.walk(os.path.join(EVALS, "fixtures")):
            for n in names:
                if "EVAL:" in read(os.path.join(root, n)):
                    annotated.add(os.path.relpath(root, os.path.join(EVALS, "fixtures")).split(os.sep)[0])
        self.assertGreaterEqual(len(annotated), 3, annotated)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class Prompts(unittest.TestCase):
    def test_prompts_are_in_step_with_the_fixtures(self):
        # Rebuilds every fixture as a real repository; the SHAs must match.
        self.assertEqual(bp.main(["--check"]), 0, "run python3 evals/build_prompts.py")


class Cases(unittest.TestCase):
    def test_every_case_has_a_prompt_a_grader_and_a_fixture(self):
        for case, fixture in bp.CASES.items():
            with self.subTest(case=case):
                self.assertTrue(os.path.exists(os.path.join(EVALS, case, "prompt.md")))
                self.assertTrue(os.path.exists(os.path.join(EVALS, case, "graders", "criteria.md")))
                for part in ("INTENT.md", "commits", "head"):
                    self.assertTrue(os.path.exists(os.path.join(EVALS, "fixtures", fixture, part)))

    def test_no_orphan_case_directories(self):
        on_disk = {d for d in os.listdir(EVALS) if os.path.exists(os.path.join(EVALS, d, "prompt.md"))}
        self.assertEqual(on_disk, set(bp.CASES))

    def test_only_the_control_has_nothing_to_analyse(self):
        for case in bp.CASES:
            self.assertEqual(scan_of(case)["analyse"], case != "nothing-in-history", case)

    def test_the_matched_pair_has_the_same_history_signal(self):
        # recall-fix-guard-removed and precision-fix-guard-kept share their
        # history; only the head differs. If the scan told them apart, the
        # pair would measure the scan, not the reviewer.
        a, b = scan_of("recall-fix-guard-removed"), scan_of("precision-fix-guard-kept")
        self.assertEqual(a["files"][0]["commits"], b["files"][0]["commits"])

    def test_graders(self):
        for case in bp.CASES:
            text = read(os.path.join(EVALS, case, "graders", "criteria.md"))
            self.assertRegex(text, re.compile(r"^type:\s*llm\s*$", re.M))
            if case.startswith("recall-"):
                self.assertIn("`REG-`", text)
                self.assertIn("critical or major", text)
            if case.startswith("precision-"):
                self.assertIn("contains no regression hunt report at all", text)


if __name__ == "__main__":
    unittest.main(verbosity=1)
