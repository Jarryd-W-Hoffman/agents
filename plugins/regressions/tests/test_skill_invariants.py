#!/usr/bin/env python3
"""Pins what keeps this plugin read-only, cheap, and tied to history.

Run: python3 tests/test_skill_invariants.py
"""

from __future__ import annotations

import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT = os.path.join(REPO, "agents", "regression-reviewer.md")
SKILL_DIR = os.path.join(REPO, "skills", "hunt")
SKILL = os.path.join(SKILL_DIR, "SKILL.md")
TEMPLATE = os.path.join(SKILL_DIR, "references", "report-template.md")
HOOKS = os.path.join(REPO, "hooks", "hooks.json")
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


def section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, f"no '## {heading}' section"
    return m.group(1)


class Agent(unittest.TestCase):
    def setUp(self):
        self.text = read(AGENT)
        self.fm = frontmatter(self.text)

    def test_name_matches_guard_scope(self):
        self.assertEqual(self.fm["name"], "regression-reviewer")

    def test_no_write_tools(self):
        for t in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            self.assertNotIn(t, csv(self.fm["tools"]))
        self.assertEqual(csv(self.fm["disallowedTools"]), {"Edit", "Write", "MultiEdit", "NotebookEdit"})

    def test_shared_sections(self):
        for heading in ("External tooling (read-only)", "Untrusted input", "Confidence scoring", "Output format"):
            section(self.text, heading)
        self.assertIn("Report only findings scoring **≥ 80**", self.text)

    def test_every_finding_rests_on_an_earlier_commit(self):
        self.assertIn("Every finding you report rests on a specific earlier commit", self.text)
        self.assertIn("Anything you cannot tie to a specific earlier commit", section(self.text, "What does not count"))

    def test_reads_commits_and_states_invariants(self):
        procedure = section(self.text, "Procedure")
        self.assertIn("**invariant**", procedure)
        self.assertIn("git show <sha>", procedure)
        # A revert is only re-introduced if its cause still holds at head.
        self.assertIn("Check that at the head; do not assume it", procedure)

    def test_moved_guard_is_not_a_finding(self):
        # The precision bait in the evals.
        self.assertIn("moving the guard to another function or file", section(self.text, "What does not count"))

    def test_reg_prefix(self):
        self.assertIn("#### [REG-1]", self.text)
        self.assertNotRegex(self.text, r"\[(COR|CMP|CPL|CNS|MIG)-\d")


class Hooks(unittest.TestCase):
    def test_guard_scoped_to_the_reviewer(self):
        (entry,) = json.loads(read(HOOKS))["hooks"]["PreToolUse"]
        command = entry["hooks"][0]["command"]
        self.assertIn("READONLY_GUARD_AGENTS='*regression-reviewer'", command)

    def test_guard_files_exist(self):
        for rel in ("readonly-guard.py", "guard/__init__.py", "guard/shell.py", "guard/mcp.py",
                    "guard/tables.py", "guard/util.py"):
            self.assertTrue(os.path.isfile(os.path.join(REPO, "hooks", rel)), rel)


class Skill(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL)
        self.fm = frontmatter(self.text)

    def test_name(self):
        self.assertEqual(self.fm["name"], "hunt")

    def test_tools(self):
        tools = csv(self.fm["allowed-tools"])
        for t in ("Agent", "Write", "Bash(git:*)", "Bash(python3:*)"):
            self.assertIn(t, tools)
        for t in ("Edit", "MultiEdit", "NotebookEdit"):
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

    def test_scans_before_launching_and_stops_without_history(self):
        step2, step3 = self.text.index("### Step 2"), self.text.index("### Step 3")
        self.assertIn("scripts/history-scan.py", self.text[step2:step3])
        self.assertIn("If `analyse` is false, stop.", self.text[step2:step3])
        self.assertIn("Do not launch the reviewer", self.text[step2:step3])

    def test_one_reviewer_and_incomplete_on_silence(self):
        self.assertIn("Launch **one** `Agent` call", self.text)
        self.assertIn("regressions:regression-reviewer", self.text)
        self.assertIn("INCOMPLETE", self.text)

    def test_findings_json(self):
        self.assertIn('scripts/finding_contract.py" <dir>/findings.json', self.text)
        self.assertIn("`pass` (always `regressions`)", self.text)

    def test_reply_is_the_report(self):
        self.assertIn("**Your reply is that report**", self.text)

    def test_contract_files_ship(self):
        for name in ("finding.schema.json", "finding_contract.py"):
            self.assertTrue(os.path.isfile(os.path.join(SKILL_DIR, "scripts", name)), name)


class Template(unittest.TestCase):
    def test_layout_and_kept_section(self):
        text = read(TEMPLATE)
        self.assertIn("`{{path}}:{{line}}` · confidence {{NN}} · regressions", text)
        self.assertIn("## Kept", text)


class Manifest(unittest.TestCase):
    def test_name_matches_directory(self):
        self.assertEqual(json.loads(read(MANIFEST))["name"], os.path.basename(REPO))


if __name__ == "__main__":
    unittest.main(verbosity=1)
