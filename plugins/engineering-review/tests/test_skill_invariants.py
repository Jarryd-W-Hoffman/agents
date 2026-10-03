#!/usr/bin/env python3
"""Pins what keeps this version a planner: no agents, no writes, the script decides.

Run: python3 tests/test_skill_invariants.py
"""

from __future__ import annotations

import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(REPO, "skills", "review")
SKILL = os.path.join(SKILL_DIR, "SKILL.md")
TEMPLATE = os.path.join(SKILL_DIR, "references", "plan-template.md")
MANIFEST = os.path.join(REPO, ".claude-plugin", "plugin.json")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "no frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        if line and not line.startswith(" "):
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def csv(value: str) -> set:
    return {t.strip() for t in value.split(",") if t.strip()}


class Skill(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL)
        self.fm = frontmatter(self.text)

    def test_name(self):
        self.assertEqual(self.fm["name"], "review")

    def test_planner_cannot_launch_or_write(self):
        # Running plugins is the next version. Until then the planner must not
        # be able to start an agent or write a file, whatever its prose says.
        tools = csv(self.fm["allowed-tools"])
        for t in ("Agent", "Write", "Edit", "MultiEdit", "NotebookEdit", "Skill"):
            self.assertNotIn(t, tools)
        for t in tools:
            if t.startswith("Bash("):
                self.assertRegex(t, r"^Bash\([^)]+:\*\)$", t)

    def test_no_launch_time_preamble(self):
        self.assertEqual(re.findall(r"!`[^`]*`", self.text), [])
        self.assertIn("git rev-parse --show-toplevel", self.text)

    def test_references_exist(self):
        for rel in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w./-]+)", self.text):
            self.assertTrue(os.path.exists(os.path.join(SKILL_DIR, rel)), rel)

    def test_the_script_decides(self):
        self.assertIn("scripts/plan.py", self.text)
        self.assertIn("Do not add a plugin it skipped or drop one it selected", self.text)

    def test_says_running_is_not_built(self):
        self.assertIn("This version only plans", self.text)

    def test_missing_plugin_is_never_clean(self):
        self.assertIn("not installed", self.text)
        self.assertIn("never as clean", self.text)


class Template(unittest.TestCase):
    def test_shows_selection_skips_and_follow_ups(self):
        text = read(TEMPLATE)
        for heading in ("## Would run", "## Skipped", "## Afterwards, if you want it"):
            self.assertIn(heading, text)
        self.assertIn("Do not add, drop or reorder plugins", text)


class Manifest(unittest.TestCase):
    def test_name_matches_directory(self):
        self.assertEqual(json.loads(read(MANIFEST))["name"], os.path.basename(REPO))


if __name__ == "__main__":
    unittest.main(verbosity=1)
