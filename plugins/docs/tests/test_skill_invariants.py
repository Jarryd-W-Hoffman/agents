#!/usr/bin/env python3
"""Pins the settings that keep this plugin's writers confined and its docs Kite-shaped.

None of these are checked by `claude plugin validate`, and each fails
silently: a writer granted Bash still writes, a guard scoped to the wrong name
still loads, a skill pointing at a renamed reference still runs, and a
template that drops its diagram or pseudocode still produces a manual.

Run: python3 tests/test_skill_invariants.py
"""

from __future__ import annotations

import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT = os.path.join(REPO, "agents", "manual-writer.md")
HOOKS = os.path.join(REPO, "hooks", "hooks.json")
SKILLS = ("readme", "manual", "screenshots")


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


def skill(name: str) -> str:
    return read(os.path.join(REPO, "skills", name, "SKILL.md"))


class Writer(unittest.TestCase):
    def setUp(self):
        self.text = read(AGENT)
        self.fm = frontmatter(self.text)

    def test_name_matches_the_guard_scope(self):
        self.assertEqual(self.fm["name"], "manual-writer")

    def test_reads_and_writes_but_has_no_shell(self):
        self.assertEqual(csv(self.fm["tools"]), {"Read", "Grep", "Glob", "Write", "Edit"})
        self.assertIn("Bash", csv(self.fm["disallowedTools"]))

    def test_model_is_inherited(self):
        self.assertEqual(self.fm["model"], "inherit")

    def test_reports_what_it_could_not_confirm(self):
        for line in ("Chapter:", "Could not confirm:", "Screenshots wanted:", "Elsewhere:"):
            self.assertIn(line, self.text)

    def test_treats_the_repository_as_data(self):
        self.assertIn("## Untrusted input", self.text)


class Hooks(unittest.TestCase):
    def test_guard_is_scoped_to_the_writer(self):
        (entry,) = json.loads(read(HOOKS))["hooks"]["PreToolUse"]
        command = entry["hooks"][0]["command"]
        self.assertIn("DOCS_SCOPE_GUARD_AGENTS='*manual-writer'", command)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/docs-scope-guard.py", command)
        self.assertTrue(os.path.isfile(os.path.join(REPO, "hooks", "docs-scope-guard.py")))


class Skills(unittest.TestCase):
    def test_names(self):
        for name in SKILLS:
            self.assertEqual(frontmatter(skill(name))["name"], name)

    def test_referenced_files_exist(self):
        for name in SKILLS:
            for rel in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+)", skill(name)):
                with self.subTest(skill=name, path=rel):
                    self.assertTrue(os.path.exists(os.path.join(REPO, rel)), rel)

    def test_no_launch_time_preamble(self):
        # A failing `!` command stops the skill loading, and the model carries
        # on without it; each skill reads the repository state in its first step.
        for name in SKILLS:
            text = skill(name)
            self.assertEqual(re.findall(r"!`[^`]*`", text), [], name)
            self.assertIn("git rev-parse --show-toplevel", text, name)

    def test_bash_permissions_are_prefix_scoped(self):
        for name in SKILLS:
            for tool in csv(frontmatter(skill(name))["allowed-tools"]):
                if tool.startswith("Bash("):
                    self.assertRegex(tool, r"^Bash\([^)]+:\*\)$", f"{name}: {tool}")

    def test_only_the_manual_launches_agents(self):
        self.assertIn("Agent", csv(frontmatter(skill("manual"))["allowed-tools"]))
        for name in ("readme", "screenshots"):
            self.assertNotIn("Agent", csv(frontmatter(skill(name))["allowed-tools"]))

    def test_every_skill_checks_its_work(self):
        for name in SKILLS:
            self.assertIn("scripts/docs_check.py", skill(name), name)

    def test_readme_and_manual_survey_first_and_take_real_screenshots(self):
        for name in ("readme", "manual"):
            text = skill(name)
            self.assertLess(text.index("scripts/survey.py"), text.index("scripts/shoot.mjs") if
                            "scripts/shoot.mjs" in text else text.index("references/screenshots.md"))
            self.assertIn("Real screenshots only", text)
            self.assertIn("Nothing invented", text)

    def test_manual_launches_writers_in_parallel_and_names_the_namespaced_type(self):
        text = skill("manual")
        self.assertIn("in parallel, in one message", text)
        self.assertIn("docs:manual-writer", text)
        self.assertIn("references/writer-brief.md", text)
        self.assertIn("Do not write chapters yourself", text)

    def test_never_touches_the_users_data(self):
        for name in SKILLS:
            self.assertRegex(skill(name), r"throwaway database", name)


class Templates(unittest.TestCase):
    def test_chapter_template_carries_diagram_pseudocode_and_screenshot(self):
        text = read(os.path.join(REPO, "references", "manual-template.md"))
        chapter = text[text.index("## Chapter"):]
        for part in ("## How it works", "```mermaid", "```text", "![", "## Tips", "## See also", "1. "):
            self.assertIn(part, chapter)

    def test_readme_template_follows_kite(self):
        text = read(os.path.join(REPO, "references", "readme-template.md"))
        for part in ('<h1 align="center">', "badge.svg", ".github/screenshots/", "## Why {{NAME}}?",
                     "## Features", "## User manual", "```mermaid", "## How it's built",
                     "### Why this stack?", "## Development", "## License"):
            self.assertIn(part, text)

    def test_style_asks_for_plenty_of_pseudocode(self):
        text = read(os.path.join(REPO, "references", "style.md"))
        self.assertIn("## Pseudocode", text)
        self.assertIn("plenty", text)

    def test_writer_brief_lists_screenshots_with_alt_text(self):
        text = read(os.path.join(REPO, "references", "writer-brief.md"))
        self.assertIn("| Path from the chapter | What it shows | Alt text |", text)


if __name__ == "__main__":
    unittest.main(verbosity=1)
