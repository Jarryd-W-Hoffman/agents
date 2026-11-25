#!/usr/bin/env python3
"""Tests for scripts/shoot.mjs that need Node but no browser: plan validation and --check.

Skipped when `node` is not on PATH. Taking real screenshots needs Playwright and a
browser, so it is checked by hand (see CONTRIBUTING.md), not here.

Run: python3 tests/test_shoot.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOOT = os.path.join(REPO, "scripts", "shoot.mjs")
NODE = shutil.which("node")


def run(plan, *args: str):
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "plan.json"), "w", encoding="utf-8") as fh:
            fh.write(plan if isinstance(plan, str) else json.dumps(plan))
        return subprocess.run([NODE, SHOOT, "plan.json", "--root", root, *args], capture_output=True,
                              text=True, timeout=30, check=False)


GOOD = {
    "baseUrl": "http://127.0.0.1:8199",
    "setup": [{"goto": "/login"}, {"fill": ["#email", "a@b.c"]}],
    "shots": [
        {"name": "hero", "out": ".github/screenshots/hero.png", "path": "/", "alt": "The app."},
        {"name": "help", "out": "docs/manual/images/help.png", "alt": "Help.",
         "terminal": {"command": "echo hi"}},
    ],
}


@unittest.skipUnless(NODE, "node is not on PATH")
class Check(unittest.TestCase):
    def test_a_good_plan_passes(self):
        result = run(GOOD, "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("hero\tpage\t.github/screenshots/hero.png", result.stdout)
        self.assertIn("help\tterminal\tdocs/manual/images/help.png", result.stdout)

    def test_only_selects_shots(self):
        result = run(GOOD, "--check", "--only", "help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("hero", result.stdout)
        self.assertEqual(run(GOOD, "--check", "--only", "nope").returncode, 2)

    def assertRejects(self, plan, message):
        result = run(plan, "--check")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(message, result.stderr)

    def shot(self, **changes):
        plan = json.loads(json.dumps(GOOD))
        plan["shots"][0].update(changes)
        return plan

    def test_rejects_a_bad_plan(self):
        self.assertRejects(self.shot(alt=""), "'alt' is required")
        self.assertRejects(self.shot(out="hero.gif"), "'out' must be a .png or .jpg path")
        self.assertRejects(self.shot(out="../outside.png"), "must stay inside the repository")
        self.assertRejects(self.shot(name="Hero Shot"), "'name' must be kebab-case")
        self.assertRejects(self.shot(name="help"), "name used twice")
        self.assertRejects(self.shot(terminal={"command": "ls"}), "a terminal or a page, not both")
        self.assertRejects(self.shot(actions=[{"teleport": "#x"}]), "unknown action")
        self.assertRejects(dict(GOOD, shots=[]), "'shots' is missing or empty")
        no_base = dict(GOOD)
        del no_base["baseUrl"]
        self.assertRejects(no_base, "'path' needs a top-level 'baseUrl'")

    def test_unreadable_plan(self):
        result = run("{not json", "--check")
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot read plan.json", result.stderr)


@unittest.skipUnless(NODE, "node is not on PATH")
class Ansi(unittest.TestCase):
    def convert(self, text: str) -> str:
        script = ("import(process.argv[1]).then(m => process.stdout.write(m.ansiToHtml(process.argv[2])))")
        result = subprocess.run([NODE, "-e", script, "file://" + SHOOT, text], capture_output=True,
                                text=True, timeout=30, check=True)
        return result.stdout

    def test_colours_become_spans_and_html_is_escaped(self):
        html = self.convert("\x1b[1;32mok\x1b[0m <b>&")
        self.assertIn('<span style="color:#a6e3a1;font-weight:700">ok</span>', html)
        self.assertTrue(html.endswith(" &lt;b&gt;&amp;"))

    def test_truecolour_and_unknown_sequences(self):
        self.assertIn("color:rgb(1,2,3)", self.convert("\x1b[38;2;1;2;3mx"))
        self.assertEqual(self.convert("a\x1b[2Kb"), "ab")


@unittest.skipUnless(NODE, "node is not on PATH")
class Markdown(unittest.TestCase):
    def convert(self, text: str) -> str:
        script = "import(process.argv[1]).then(m => process.stdout.write(m.markdownToHtml(process.argv[2])))"
        result = subprocess.run([NODE, "-e", script, "file://" + SHOOT, text], capture_output=True,
                                text=True, timeout=30, check=True)
        return result.stdout

    def test_headings_bold_code_and_lists(self):
        html = self.convert("# Plan: `HEAD`\n\n**Changed:** 3 files\n- one\n1. two")
        self.assertIn('<div class="h h1">Plan: <code>HEAD</code></div>', html)
        self.assertIn('<div class="para"><b>Changed:</b> 3 files</div>', html)
        self.assertIn('<span class="m">•</span><span>one</span>', html)
        self.assertIn('<span class="m">1.</span><span>two</span>', html)

    def test_tables_and_fences(self):
        html = self.convert("| A | B |\n|---|---|\n| `x` | y |\n\n```json\n{\"a\": 1}\n```")
        self.assertIn("<table><tr><th>A</th><th>B</th></tr><tr><td><code>x</code></td><td>y</td></tr></table>", html)
        self.assertIn('<pre class="code">{&quot;a&quot;: 1}</pre>'.replace("&quot;", '"'), html)

    def test_html_in_the_output_is_escaped(self):
        self.assertIn("&lt;script&gt;", self.convert("<script>alert(1)</script>"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
