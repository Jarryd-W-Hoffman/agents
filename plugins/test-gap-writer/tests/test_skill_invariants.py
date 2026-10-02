#!/usr/bin/env python3
"""Pins the settings of this plugin that keep "the writer adds tests and does
nothing else" true, so a well-meant edit cannot quietly widen it.

The agent's tool grants, the guard's scope, the skill's tool grants, the fixed
outcome vocabulary the skill tabulates mechanically, and the files the skill
tells the lead to read. None of these are checked by `claude plugin validate`.

Run: python3 tests/test_skill_invariants.py
"""

from __future__ import annotations

import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT = os.path.join(REPO, "agents", "test-writer.md")
SKILL_DIR = os.path.join(REPO, "skills", "write-tests")
SKILL = os.path.join(SKILL_DIR, "SKILL.md")
HOOKS = os.path.join(REPO, "hooks", "hooks.json")
MANIFEST = os.path.join(REPO, ".claude-plugin", "plugin.json")

OUTCOMES = ("REPRODUCED", "COVERED", "NOT_REPRODUCED", "BLOCKED", "NOT_WRITTEN")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text: str) -> dict:
    """A deliberately small YAML reader: top-level `key: value` pairs only.

    Block scalars (`|`, `>-`) are captured as their first line, which is all
    these tests need. Good enough to avoid a YAML dependency.
    """
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


class AgentFrontmatter(unittest.TestCase):
    def setUp(self):
        self.text = read(AGENT)
        self.fm = frontmatter(self.text)

    def test_name_matches_filename_and_guard_scope(self):
        self.assertEqual(self.fm["name"], "test-writer")

    def test_tools_are_exactly_the_writing_set(self):
        self.assertEqual(csv(self.fm["tools"]), {"Read", "Grep", "Glob", "Bash", "Edit", "Write"})

    def test_bulk_and_network_tools_are_disallowed(self):
        self.assertTrue({"MultiEdit", "NotebookEdit", "WebFetch", "WebSearch"}
                        <= csv(self.fm["disallowedTools"]))

    def test_no_mcp_grant(self):
        self.assertNotIn("mcp__", self.fm["tools"])

    def test_model_is_inherited(self):
        self.assertEqual(self.fm["model"], "inherit")

    def test_description_starts_with_the_convention_and_has_examples(self):
        self.assertIn("Use this agent when", self.text.split("tools:")[0])
        self.assertGreaterEqual(self.text.count("<example>"), 2)


class AgentBody(unittest.TestCase):
    def setUp(self):
        self.text = read(AGENT)

    def test_has_untrusted_input_section(self):
        self.assertIn("## Untrusted input", self.text)

    def test_names_every_outcome(self):
        for word in OUTCOMES:
            self.assertIn(word, self.text, word)

    def test_tells_the_writer_a_guard_denial_is_final(self):
        self.assertRegex(self.text, r"(?i)never work around")

    def test_forbids_editing_source_and_weakening_tests(self):
        self.assertRegex(self.text, r"(?i)never edit production code")
        self.assertRegex(self.text, r"(?i)never delete, rename, skip, loosen or rewrite an existing test")

    def test_never_overwrites_an_existing_file(self):
        # Two writers on one module both creating the same test file was the
        # first bug the end-to-end run found; the guard denies it and the
        # agent has to know to extend instead.
        self.assertRegex(self.text, r"(?i)never use `Write` on a path that exists")

    def test_output_format_carries_the_fields_the_skill_merges(self):
        for field in ("**Outcome:**", "**Ran:**", "**Result:**", "**Meaning:**", "### Files"):
            self.assertIn(field, self.text, field)


class GuardScope(unittest.TestCase):
    def test_hook_runs_the_guard_scoped_to_the_writer(self):
        hooks = json.loads(read(HOOKS))
        commands = [h["command"] for group in hooks["hooks"]["PreToolUse"] for h in group["hooks"]]
        self.assertEqual(len(commands), 1)
        cmd = commands[0]
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/test-scope-guard.py", cmd)
        m = re.search(r"TEST_SCOPE_GUARD_AGENTS='([^']*)'", cmd)
        self.assertIsNotNone(m, "guard is not scoped; it would apply to the main session")
        self.assertTrue(all(g.endswith("test-writer") for g in m.group(1).split(",")), m.group(1))

    def test_guard_entry_point_exists(self):
        self.assertTrue(os.path.exists(os.path.join(REPO, "hooks", "test-scope-guard.py")))


class SkillFrontmatter(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL)
        self.fm = frontmatter(self.text)

    def test_name(self):
        self.assertEqual(self.fm["name"], "write-tests")

    def test_lead_can_launch_writers_and_run_the_parser(self):
        tools = csv(self.fm["allowed-tools"])
        self.assertIn("Agent", tools)
        self.assertIn("Bash(python3:*)", tools)
        self.assertIn("Bash(git:*)", tools)

    def test_lead_cannot_edit_files(self):
        tools = csv(self.fm["allowed-tools"])
        for t in ("Edit", "MultiEdit", "NotebookEdit"):
            self.assertNotIn(t, tools, f"the lead must not have {t}; writers write")

    def test_bash_rules_use_prefix_spelling(self):
        for t in csv(self.fm["allowed-tools"]):
            if t.startswith("Bash("):
                self.assertRegex(t, r"^Bash\([^)]+:\*\)$", t)


class SkillBody(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL)

    def test_references_exist(self):
        for rel in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w./-]+)", self.text):
            self.assertTrue(os.path.exists(os.path.join(SKILL_DIR, rel)), rel)

    def test_reads_the_brief_and_the_template_and_runs_the_parser(self):
        self.assertIn("references/writer-brief.md", self.text)
        self.assertIn("references/report-template.md", self.text)
        self.assertIn("scripts/extract-findings.py", self.text)

    def test_names_the_namespaced_agent_type(self):
        self.assertIn("test-gap-writer:test-writer", self.text)

    def test_launches_writers_in_one_message(self):
        self.assertRegex(self.text, r"(?i)single message|one message")

    def test_same_path_findings_run_in_waves(self):
        self.assertRegex(self.text, r"(?i)wave")

    def test_preamble_commands_are_plain_git(self):
        # The `!` lines run under the skill's own allowed-tools. A pipe into
        # sed or head is not `Bash(git:*)`, and in headless mode that blocked
        # the preamble and the skill body never loaded.
        for line in re.findall(r"!`([^`]*)`", self.text):
            self.assertTrue(line.startswith("git "), line)
            for bad in ("|", "||", "2>", "&&", ";"):
                self.assertNotIn(bad, line, line)

    def test_names_every_outcome(self):
        for word in OUTCOMES:
            self.assertIn(word, self.text, word)

    def test_never_commits_or_posts(self):
        self.assertRegex(self.text, r"(?i)never commit")

    def test_checks_for_writes_outside_test_paths(self):
        self.assertIn("git status", self.text)
        self.assertIn("Source files touched", self.text)


class FindingContract(unittest.TestCase):
    """Findings JSON is checked against the contract, and preferred over parsing a report."""

    def setUp(self):
        self.text = read(SKILL)

    def test_contract_files_ship_with_the_skill(self):
        for name in ("finding.schema.json", "finding_contract.py"):
            self.assertTrue(os.path.isfile(os.path.join(SKILL_DIR, "scripts", name)),
                            f"scripts/{name} is missing; run scripts/sync-shared.py --write")

    def test_findings_json_is_validated(self):
        self.assertIn('scripts/finding_contract.py" <findings.json>', self.text)

    def test_sibling_findings_json_is_preferred_over_parsing(self):
        # The report's layout belongs to four-pass-review and may change; the
        # contract may not. Parsing is the fallback.
        self.assertIn("findings.json` sits in the same directory", self.text)

    def test_default_selection_is_an_allow_list(self):
        # A new plugin's pass (migration-safety) must not be selected by
        # default just because nobody added it to a deny list.
        self.assertIn("drop every finding whose `pass` is not `correctness`, `completeness` or `adhoc`",
                      self.text)

    def test_invalid_input_is_refused_not_repaired(self):
        self.assertIn("Do not repair the file yourself", self.text)


class ReportTemplate(unittest.TestCase):
    def test_table_has_the_merge_columns(self):
        text = read(os.path.join(SKILL_DIR, "references", "report-template.md"))
        self.assertIn("| Finding | Test | Outcome | Result | Meaning |", text)
        self.assertIn("Source files touched", text)


class Manifest(unittest.TestCase):
    def test_name_matches_directory(self):
        self.assertEqual(json.loads(read(MANIFEST))["name"], os.path.basename(REPO))


if __name__ == "__main__":
    unittest.main()
