#!/usr/bin/env python3
"""Pins the settings that keep this plugin read-only, cheap, and readable by others.

None of these are checked by `claude plugin validate`, and each one fails
silently: an agent granted Write still reviews, a guard scoped to the wrong
name still loads, a skill that launches the reviewer without the early stop
still produces a report, and a findings.json in the wrong shape is only
noticed by the plugin that tries to read it.

Run: python3 tests/test_skill_invariants.py
"""

from __future__ import annotations

import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT = os.path.join(REPO, "agents", "migration-reviewer.md")
SKILL_DIR = os.path.join(REPO, "skills", "check")
SKILL = os.path.join(SKILL_DIR, "SKILL.md")
BRIEF = os.path.join(SKILL_DIR, "references", "reviewer-brief.md")
TEMPLATE = os.path.join(SKILL_DIR, "references", "report-template.md")
HOOKS = os.path.join(REPO, "hooks", "hooks.json")
MANIFEST = os.path.join(REPO, ".claude-plugin", "plugin.json")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text: str) -> dict:
    """Top-level `key: value` pairs only; a block scalar is captured as its first line."""
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

    def test_name_matches_filename_and_guard_scope(self):
        self.assertEqual(self.fm["name"], "migration-reviewer")

    def test_no_write_tools(self):
        tools = csv(self.fm["tools"])
        for t in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            self.assertNotIn(t, tools, f"the reviewer is read-only; {t} must not be granted")
        self.assertEqual(csv(self.fm["disallowedTools"]),
                         {"Edit", "Write", "MultiEdit", "NotebookEdit"})

    def test_model_is_inherited(self):
        self.assertEqual(self.fm["model"], "inherit")

    def test_has_the_sections_shared_with_the_four_pass_reviewers(self):
        # Same headings and rubric as four-pass-review's agents, so reports
        # from the two plugins mean the same thing by the same number.
        for heading in ("External tooling (read-only)", "Untrusted input",
                        "Confidence scoring", "Output format"):
            section(self.text, heading)
        self.assertIn("Report only findings scoring **≥ 80**", self.text)

    def test_forbids_running_migrations_or_touching_a_database(self):
        inputs = section(self.text, "Inputs & scope resolution")
        for word in ("Never run a migration", "artisan", "--pretend", "database client"):
            self.assertIn(word, inputs)

    def test_reads_code_at_both_revisions(self):
        # The deploy window is old code against the new schema. A reviewer
        # that only reads the head cannot see it.
        self.assertIn("at both revisions", self.text)
        self.assertIn("git grep -n '<column>' <base>", self.text)

    def test_judges_against_a_stated_deploy_model(self):
        section(self.text, "The deploy model")
        self.assertIn("**Deploy model:**", self.text)

    def test_ids_use_the_mig_prefix(self):
        self.assertIn("#### [MIG-1]", self.text)
        self.assertNotRegex(self.text, r"\[(COR|CMP|CPL|CNS)-\d")

    def test_expand_contract_second_half_is_not_a_finding(self):
        # The precision bait in the evals: dropping a column nothing at base
        # still uses is the safe step. Losing this line is how the reviewer
        # starts crying wolf on every drop.
        self.assertIn("A dropped column that nothing references at base", self.text)


class Hooks(unittest.TestCase):
    def test_guard_is_scoped_to_the_reviewer(self):
        (entry,) = json.loads(read(HOOKS))["hooks"]["PreToolUse"]
        command = entry["hooks"][0]["command"]
        self.assertIn("READONLY_GUARD_AGENTS='*migration-reviewer'", command)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/readonly-guard.py", command)

    def test_guard_entry_point_and_package_exist(self):
        for rel in ("readonly-guard.py", "guard/__init__.py", "guard/shell.py",
                    "guard/mcp.py", "guard/tables.py", "guard/util.py"):
            self.assertTrue(os.path.isfile(os.path.join(REPO, "hooks", rel)), rel)


class Skill(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL)
        self.fm = frontmatter(self.text)

    def test_name(self):
        self.assertEqual(self.fm["name"], "check")

    def test_tools(self):
        tools = csv(self.fm["allowed-tools"])
        for t in ("Agent", "Write", "Bash(git:*)", "Bash(python3:*)"):
            self.assertIn(t, tools)
        for t in ("Edit", "MultiEdit", "NotebookEdit"):
            self.assertNotIn(t, tools)
        for t in tools:
            if t.startswith("Bash("):
                self.assertRegex(t, r"^Bash\([^)]+:\*\)$", t)

    def test_preamble_commands_are_plain_git(self):
        # A pipe in a `!` line is not `Bash(git:*)` and blocks the preamble headless.
        for line in re.findall(r"!`([^`]*)`", self.text):
            self.assertTrue(line.startswith("git "), line)
            for bad in ("|", "2>", "&&", ";"):
                self.assertNotIn(bad, line, line)

    def test_references_exist(self):
        for rel in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w./-]+)", self.text):
            self.assertTrue(os.path.exists(os.path.join(SKILL_DIR, rel)), rel)

    def test_finds_migrations_before_launching_the_reviewer(self):
        # The cost model: no migrations, no agent.
        step2 = self.text.index("### Step 2")
        step3 = self.text.index("### Step 3")
        self.assertLess(self.text.index("scripts/find-migrations.py"), step3)
        self.assertIn("If `migrations` is empty, stop.", self.text[step2:step3])
        self.assertIn("Do not launch the reviewer", self.text[step2:step3])

    def test_one_reviewer(self):
        self.assertIn("Launch **one** `Agent` call", self.text)
        self.assertIn("migration-safety:migration-reviewer", self.text)

    def test_reviewer_silence_is_incomplete(self):
        self.assertIn("INCOMPLETE", self.text)
        self.assertIn("INCOMPLETE", read(TEMPLATE))

    def test_writes_and_validates_findings_json(self):
        self.assertIn('scripts/finding_contract.py" <dir>/findings.json', self.text)
        self.assertIn("`pass` (always `migration-safety`)", self.text)

    def test_never_runs_migrations(self):
        rules = section(self.text, "Rules")
        self.assertIn("never run a migration", rules)


class ContractFiles(unittest.TestCase):
    def test_contract_ships_with_the_skill(self):
        for name in ("finding.schema.json", "finding_contract.py"):
            self.assertTrue(os.path.isfile(os.path.join(SKILL_DIR, "scripts", name)),
                            f"scripts/{name} is missing; run scripts/sync-shared.py --write")

    def test_template_matches_the_parsers_layout(self):
        # test-gap-writer's fallback parser reads this layout; the pass name
        # in the location line is what it attributes the finding to.
        text = read(TEMPLATE)
        self.assertIn("`{{path}}:{{line}}` · confidence {{NN}} · migration-safety", text)
        self.assertIn("(confidence {{NN}}, migration-safety)", text)


class Brief(unittest.TestCase):
    def test_brief_carries_both_revisions_and_the_statuses(self):
        text = read(BRIEF)
        self.assertIn("git show {{BASE_REF_OR_SHA}}:<path>", text)
        self.assertIn("git grep -n <pattern> {{BASE_REF_OR_SHA}}", text)
        self.assertIn("OUT OF ORDER", text)


class Manifest(unittest.TestCase):
    def test_name_matches_directory(self):
        self.assertEqual(json.loads(read(MANIFEST))["name"], os.path.basename(REPO))


if __name__ == "__main__":
    unittest.main(verbosity=1)
