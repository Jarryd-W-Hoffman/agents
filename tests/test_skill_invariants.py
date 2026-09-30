#!/usr/bin/env python3
"""Invariants of the review skill that are security-relevant, not stylistic.

These pin instructions whose loss is silent. Nothing else in the suite reads
SKILL.md, so a well-meaning edit can undo them and every other check still
passes.

Both invariants here have been broken once already:

  * the skill's `allowed-tools` once granted neither `Write` nor `python3`, so
    the `--comment` path it documents could not run at all;
  * `--since` was added as "replace the base", which silently moved the
    revision the compliance pass reads rules from onto a commit belonging to
    the change -- letting an incremental re-review adopt a rule that change
    had itself added.

Run: python3 tests/test_skill_invariants.py
"""

from __future__ import annotations

import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(REPO, "skills", "review", "SKILL.md")
BRIEF = os.path.join(REPO, "skills", "review", "references", "reviewer-prompt.md")
TEMPLATE = os.path.join(REPO, "skills", "review", "references", "report-template.md")


class Contains(unittest.TestCase):
    """assertIn on a whole file dumps the file; these say what is missing."""

    maxDiff = None

    def assert_contains(self, haystack: str, needle: str, where: str, why: str):
        if needle not in haystack:
            self.fail(f"{where} no longer contains {needle!r}\n  why it matters: {why}")

    def assert_absent(self, haystack: str, needle: str, where: str, why: str):
        if needle in haystack:
            self.fail(f"{where} still contains {needle!r}\n  why it matters: {why}")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text: str) -> dict[str, str]:
    end = text.index("\n---\n", 3)
    fields, key = {}, None
    for line in text[4:end].splitlines():
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            key = m.group(1)
            fields[key] = m.group(2).strip()
        elif key:
            fields[key] += " " + line.strip()
    return fields


class AllowedTools(Contains):
    """The skill must be able to run every path it documents."""

    def setUp(self):
        self.text = read(SKILL)
        self.allowed = frontmatter(self.text).get("allowed-tools", "")

    def test_comment_path_has_the_tools_it_needs(self):
        # Step 5 writes findings.json and summary.md, then runs post-review.py.
        self.assert_contains(self.allowed, "Write", "allowed-tools",
                             "--comment writes findings.json and summary.md")
        self.assert_contains(self.allowed, "python3", "allowed-tools",
                             "--comment runs scripts/post-review.py")

    def test_bash_rules_use_the_prefix_form(self):
        # `Bash(git *)` is not the spelling permission rules take; `Bash(git:*)`
        # is. The wrong form silently matches nothing.
        for rule in re.findall(r"Bash\(([^)]*)\)", self.allowed):
            with self.subTest(rule=rule):
                self.assertNotRegex(
                    rule, r"\s\*$",
                    f"`Bash({rule})` uses the space-glob form; use `prefix:*`")

    def test_no_write_tools_beyond_write(self):
        for tool in ("Edit", "MultiEdit", "NotebookEdit"):
            self.assertNotIn(tool, self.allowed,
                             f"the skill is read-only apart from its two temp files; {tool} is not needed")


class RuleBase(Contains):
    """Written rules bind at the rule base. `--since` must not move it."""

    def setUp(self):
        self.skill = read(SKILL)
        self.brief = read(BRIEF)

    def test_skill_distinguishes_the_two_bases(self):
        for term in ("review base", "rule base"):
            self.assert_contains(self.skill, term, "SKILL.md",
                                 "the two bases must stay distinct")

    def test_rules_are_enumerated_and_read_at_the_rule_base(self):
        why = ("under --since the review base is a commit inside the change, so "
               "reading rules there lets the change supply its own rules")
        self.assert_contains(self.skill, "git ls-tree -r --name-only <rule base>",
                             "SKILL.md", why)
        self.assert_contains(self.skill, "git show <rule base>:<path>", "SKILL.md", why)

    def test_rules_are_never_read_from_the_working_tree(self):
        self.assert_absent(
            self.skill, "git ls-files '*CLAUDE.md'", "SKILL.md",
            "git ls-files lists the checked-out branch, which on a PR target is "
            "not the change under review")

    def test_since_moves_only_the_review_base(self):
        m = re.search(r"With `--since <ref>`[^\n]*", self.skill)
        self.assertIsNotNone(m, "the --since paragraph is gone")
        sentence = m.group(0)
        self.assertIn("review base", sentence)
        self.assertIn("rule base", sentence.lower())

    def test_brief_carries_both_bases(self):
        for ph in ("{{REVIEW_BASE_REF_OR_SHA}}", "{{RULE_BASE_REF_OR_SHA}}"):
            self.assert_contains(self.brief, ph, "reviewer-prompt.md",
                                 "reviewers cannot honour a distinction the brief omits")

    def test_brief_points_reviewers_at_the_rule_base_for_rules(self):
        self.assert_contains(self.brief, "git show {{RULE_BASE_REF_OR_SHA}}:<path>",
                             "reviewer-prompt.md",
                             "the compliance pass reads rules from wherever the brief says")

    def test_changed_rule_sources_are_reported_not_adopted(self):
        why = "a change that edits a rule file must have the edit surfaced, not obeyed"
        self.assert_contains(self.skill, "Rule sources changed by this change",
                             "SKILL.md", why)
        self.assert_contains(self.brief, "Rule sources changed by this change",
                             "reviewer-prompt.md", why)
        self.assert_contains(self.brief, "do not adopt it", "reviewer-prompt.md", why)


class Coverage(Contains):
    """A pass that did not run must not produce a clean verdict."""

    def setUp(self):
        self.skill = read(SKILL)
        self.template = read(TEMPLATE)

    def test_skill_checks_coverage_before_computing_a_verdict(self):
        why = ("a crashed pass reports nothing, not 'nothing wrong'; without "
               "this, --comment can APPROVE a pull request off a broken review")
        self.assert_contains(self.skill, "INCOMPLETE", "SKILL.md", why)
        self.assert_contains(self.template, "INCOMPLETE", "report-template.md", why)

    def test_incomplete_is_in_the_posters_verdict_table(self):
        poster = read(os.path.join(REPO, "skills", "review", "scripts",
                                   "post-review.py"))
        self.assert_contains(poster, '"INCOMPLETE": "COMMENT"', "post-review.py",
                             "an unmapped verdict silently falls back, which is "
                             "right by luck rather than by design")


class IncrementalHonesty(Contains):
    """An incremental PASS is not a verdict on the whole change."""

    def test_report_marks_an_incremental_review(self):
        self.assert_contains(read(TEMPLATE).lower(), "incremental", "report-template.md",
                             "an incremental PASS is not a verdict on the whole change")

    def test_skill_says_to_mark_it(self):
        self.assert_contains(read(SKILL).lower(), "incremental", "SKILL.md",
                             "an incremental PASS is not a verdict on the whole change")


if __name__ == "__main__":
    unittest.main(verbosity=1)
