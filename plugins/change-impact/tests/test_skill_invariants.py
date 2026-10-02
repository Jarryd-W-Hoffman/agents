#!/usr/bin/env python3
"""Pins the settings that keep this plugin read-only, cheap, and a map rather than a review.

None of these are checked by `claude plugin validate`, and each fails
silently: an agent granted Write still analyses, a guard scoped to the wrong
name still loads, a skill without the early stop still produces a map, and a
map that grows severities quietly turns into a fifth reviewer.

Run: python3 tests/test_skill_invariants.py
"""

from __future__ import annotations

import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT = os.path.join(REPO, "agents", "impact-analyst.md")
SKILL_DIR = os.path.join(REPO, "skills", "map")
SKILL = os.path.join(SKILL_DIR, "SKILL.md")
BRIEF = os.path.join(SKILL_DIR, "references", "analyst-brief.md")
TEMPLATE = os.path.join(SKILL_DIR, "references", "report-template.md")
SCHEMA = os.path.join(SKILL_DIR, "scripts", "impact.schema.json")
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


def json_block(text: str) -> str:
    blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
    assert blocks, "no json block"
    return blocks[-1]


class Agent(unittest.TestCase):
    def setUp(self):
        self.text = read(AGENT)
        self.fm = frontmatter(self.text)

    def test_name_matches_filename_and_guard_scope(self):
        self.assertEqual(self.fm["name"], "impact-analyst")

    def test_no_write_tools(self):
        tools = csv(self.fm["tools"])
        for t in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            self.assertNotIn(t, tools)
        self.assertEqual(csv(self.fm["disallowedTools"]),
                         {"Edit", "Write", "MultiEdit", "NotebookEdit"})

    def test_model_is_inherited(self):
        self.assertEqual(self.fm["model"], "inherit")

    def test_shared_sections(self):
        for heading in ("External tooling (read-only)", "Untrusted input", "Output format"):
            section(self.text, heading)

    def test_is_a_map_not_a_review(self):
        scope = section(self.text, "Out of scope")
        self.assertIn("Whether the change is right", scope)
        self.assertNotRegex(self.text, r"\*\*Verdict:\*\*|\*\*Severity:\*\*|\*\*Confidence:\*\*")

    def test_verifies_the_scan_and_finds_what_grep_misses(self):
        procedure = section(self.text, "Procedure")
        self.assertIn("Verify the scan's references", procedure)
        self.assertIn("Drop name collisions", procedure)
        for laravel in ("EventServiceProvider", "routes/console.php", "Route::resource",
                        "ShouldQueue", "Gate::policy"):
            self.assertIn(laravel, procedure)

    def test_names_serialized_jobs_as_a_contract(self):
        self.assertIn("jobs already serialized on the queue", self.text)

    def test_json_example_names_exactly_the_contract_fields(self):
        # The lead writes the agent's JSON to impact.json; a field the example
        # invents is a field the validator rejects.
        example = json_block(self.text)
        schema = json.loads(read(SCHEMA))
        top = set(re.findall(r'^\s*"(\w+)":', example.split("\n", 1)[1], re.M)) | {
            "version", "target", "base", "head", "mode"}
        self.assertLessEqual(set(schema["properties"]) - top, set(),
                             "the example omits a required top-level field")
        for key in schema["properties"]:
            self.assertIn(f'"{key}"', example, key)


class Hooks(unittest.TestCase):
    def test_guard_is_scoped_to_the_analyst(self):
        (entry,) = json.loads(read(HOOKS))["hooks"]["PreToolUse"]
        command = entry["hooks"][0]["command"]
        self.assertIn("READONLY_GUARD_AGENTS='*impact-analyst'", command)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/readonly-guard.py", command)

    def test_guard_files_exist(self):
        for rel in ("readonly-guard.py", "guard/__init__.py", "guard/shell.py",
                    "guard/mcp.py", "guard/tables.py", "guard/util.py"):
            self.assertTrue(os.path.isfile(os.path.join(REPO, "hooks", rel)), rel)


class Skill(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL)
        self.fm = frontmatter(self.text)

    def test_name(self):
        self.assertEqual(self.fm["name"], "map")

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
        # A failing `!` command stops the skill loading, and the model carries
        # on without it. Measured: `git rev-parse --abbrev-ref HEAD` failed in a
        # repository with no commits and every eval run lost the skill.
        self.assertEqual(re.findall(r"!`[^`]*`", self.text), [])
        self.assertIn("git rev-parse --show-toplevel", self.text)
    def test_references_exist(self):
        for rel in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w./-]+)", self.text):
            self.assertTrue(os.path.exists(os.path.join(SKILL_DIR, rel)), rel)

    def test_scans_before_launching_and_stops_when_nothing_to_map(self):
        step2, step3 = self.text.index("### Step 2"), self.text.index("### Step 3")
        self.assertIn("scripts/impact-scan.py", self.text[step2:step3])
        self.assertIn("If `analyse` is false, stop.", self.text[step2:step3])
        self.assertIn("Do not launch the analyst", self.text[step2:step3])

    def test_quick_mode_launches_nothing_and_says_unverified(self):
        step2, step3 = self.text.index("### Step 2"), self.text.index("### Step 3")
        quick = self.text[step2:step3]
        self.assertIn("--impact-json", quick)
        self.assertIn("skip Step 3", quick)
        self.assertIn("unverified", quick)

    def test_one_analyst(self):
        self.assertIn("Launch **one** `Agent` call", self.text)
        self.assertIn("change-impact:impact-analyst", self.text)

    def test_validates_the_map(self):
        self.assertIn('scripts/impact_contract.py" <dir>/impact.json', self.text)

    def test_lead_does_not_add_facts(self):
        self.assertIn("Do not add callers, entry points or risks of your own", self.text)

    def test_no_verdicts(self):
        rules = section(self.text, "Rules")
        self.assertIn("Facts, not findings", rules)


class Template(unittest.TestCase):
    def test_quick_mode_is_marked(self):
        text = read(TEMPLATE)
        self.assertIn("quick — script only, names matched, unverified", text)
        self.assertIn("unverified", text)


class Brief(unittest.TestCase):
    def test_carries_the_scan_and_both_revisions(self):
        text = read(BRIEF)
        self.assertIn("{{SCAN_JSON}}", text)
        self.assertIn("git show {{BASE_REF_OR_SHA}}:<path>", text)


class Manifest(unittest.TestCase):
    def test_name_matches_directory(self):
        self.assertEqual(json.loads(read(MANIFEST))["name"], os.path.basename(REPO))


if __name__ == "__main__":
    unittest.main(verbosity=1)
