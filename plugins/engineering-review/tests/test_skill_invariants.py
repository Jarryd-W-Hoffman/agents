#!/usr/bin/env python3
"""Pins what keeps the orchestrator honest: the script selects, the merge decides,
every plugin runs unmodified in its own subagent, and nothing that did not run
counts as clean.

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

    def test_tools(self):
        tools = csv(self.fm["allowed-tools"])
        for t in ("Agent", "Write", "Bash(git:*)", "Bash(python3:*)"):
            self.assertIn(t, tools)
        # The lead never edits the repository, and never runs a plugin's skill
        # in its own context: each runs in its own subagent.
        for t in ("Edit", "MultiEdit", "NotebookEdit", "Skill"):
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

    def test_plan_flag_launches_nothing(self):
        step3 = self.text[self.text.index("### Step 3"):self.text.index("### Step 4")]
        self.assertIn("With `--plan`, that is your whole reply. Stop.", step3)
        self.assertIn("If nothing is selected, stop", step3)

    def test_plugins_run_in_parallel_each_in_its_own_subagent(self):
        step4 = self.text[self.text.index("### Step 4"):self.text.index("### Step 5")]
        self.assertIn("**in a single message**", step4)
        self.assertIn("`general-purpose`", step4)
        self.assertIn("runner-brief.md", step4)

    def test_merge_decides_the_verdict(self):
        step5 = self.text[self.text.index("### Step 5"):self.text.index("### Step 6")]
        self.assertIn("scripts/merge.py", step5)
        self.assertIn("Never record a plugin as `reported` or `nothing_to_do` unless its subagent said so",
                      step5)

    def test_follow_ups_are_offered_never_run(self):
        self.assertIn("**Do not run a follow-up.**", self.text)

    def test_plugins_run_unmodified(self):
        rules = self.text[self.text.index("## Rules"):]
        self.assertIn("Do not pass a plugin `--comment`", rules)

    def test_reply_is_the_report(self):
        self.assertIn("**Your reply is that report**", self.text)

    def test_missing_plugin_is_never_clean(self):
        self.assertIn("not installed", self.text)
        self.assertIn("A plugin that did not run is never a clean result", self.text)


class Template(unittest.TestCase):
    def test_report_names_what_did_not_run(self):
        text = read(os.path.join(SKILL_DIR, "references", "report-template.md"))
        self.assertIn("`INCOMPLETE` names every plugin that did not report", text)
        self.assertIn("Do not add, drop, merge or reword findings", text)

    def test_runner_reply_block(self):
        text = read(os.path.join(SKILL_DIR, "references", "runner-brief.md"))
        for field in ("STATUS:", "FINDINGS:", "IMPACT:", "REPORT:", "VERDICT:", "REASON:"):
            self.assertIn(field, text)
        self.assertIn("No other flags", text)
        # The contract file is the result; a missing markdown report is a note.
        self.assertIn("this is still reported", text)
        # Measured: subagents share the session scratchpad, and one plugin
        # picked up a file an earlier run had left there.
        self.assertIn("make a fresh directory for this plugin's output with `mktemp -d`", text)

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
