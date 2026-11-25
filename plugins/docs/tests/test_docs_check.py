#!/usr/bin/env python3
"""Tests for scripts/docs_check.py: the checks a README and manual must pass.

Run: python3 tests/test_docs_check.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import tempfile
import textwrap
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("docs_check", os.path.join(REPO, "scripts", "docs_check.py"))
docs_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs_check)

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16

GOOD_CHAPTER = textwrap.dedent("""\
    # Links

    Links make a vault more than a pile of notes.

    ![Typing a link, with a match offered.](images/links.png)

    ## How it works

    ```mermaid
    flowchart LR
        A["Home"] -->|link| B["Kite launch"]
    ```

    ```text
    when a note is saved:
      for each link in it:
        if the target exists, record it
        else record an unresolved link
    ```

    ## Make a link

    1. Type `[[`.
    2. Press <kbd>Enter</kbd>.

    | You write | It links to |
    | --- | --- |
    | `[[Note]]` | the note |

    ## Tips

    - **Rename:** links follow.

    ## See also

    - [Search](02-search.md#find-a-note)
    """)

SEARCH_CHAPTER = GOOD_CHAPTER.replace("# Links", "# Search").replace(
    "## Make a link", "## Find a note").replace("(02-search.md#find-a-note)", "(01-links.md#make-a-link)")

INDEX = textwrap.dedent("""\
    # Manual

    ![The app.](images/links.png)

    | | Page | What's in it |
    | --- | --- | --- |
    | 🔗 | [Links](01-links.md) | Links |
    | 🔎 | [Search](02-search.md) | Search |

    ## Conventions

    ## About the screenshots
    """)

README = textwrap.dedent("""\
    <h1 align="center">Demo</h1>

    <p align="center"><img src=".github/screenshots/hero.png" alt="The main screen." width="900"></p>

    <p align="center">
        <a href="#why-demo">Why Demo?</a> · <a href="#features">Features</a> ·
        <a href="#how-its-built">How it's built</a> · <a href="#development">Development</a> ·
        <a href="#license">License</a>
    </p>

    ## Why Demo?

    ## Features

    > 📖 The [user manual](docs/manual/README.md) covers every feature.

    ![The graph.](.github/screenshots/hero.png)

    ## How it's built

    ```mermaid
    flowchart LR
        A --> B
    ```

    ## Development

    ## License
    """)


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def write(self, rel: str, content) -> None:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb" if isinstance(content, bytes) else "w", encoding=None if isinstance(content, bytes) else "utf-8") as fh:
            fh.write(content)

    def good(self) -> "Fixture":
        self.write("README.md", README)
        self.write(".github/screenshots/hero.png", PNG)
        self.write("docs/manual/README.md", INDEX)
        self.write("docs/manual/01-links.md", GOOD_CHAPTER)
        self.write("docs/manual/02-search.md", SEARCH_CHAPTER)
        self.write("docs/manual/images/links.png", PNG)
        return self

    def run(self, **kw):
        kw.setdefault("readme", "README.md")
        kw.setdefault("manual", "docs/manual")
        kw.setdefault("plan", None)
        return docs_check.run(self.root, kw["readme"], kw["manual"], kw["plan"])


def messages(items) -> list[str]:
    return [f"{i['path']}: {i['message']}" for i in items]


class Slug(unittest.TestCase):
    def test_matches_github(self):
        self.assertEqual(docs_check.slug("Why Kite?"), "why-kite")
        self.assertEqual(docs_check.slug("How it's built"), "how-its-built")
        self.assertEqual(docs_check.slug("🔎 Finding"), "-finding")
        self.assertEqual(docs_check.slug("`Mod+K` and more"), "modk-and-more")
        self.assertEqual(docs_check.slug("Your vault on disk"), "your-vault-on-disk")

    def test_duplicate_headings_are_numbered(self):
        self.assertEqual(docs_check.anchors("## Tips\n\n## Tips\n"), {"tips", "tips-1"})

    def test_headings_in_code_are_not_anchors(self):
        self.assertEqual(docs_check.anchors("```bash\n# not a heading\n```\n## Real\n"), {"real"})


class Clean(unittest.TestCase):
    def test_a_kite_shaped_readme_and_manual_pass(self):
        report = Fixture().good().run()
        self.assertEqual(messages(report.errors), [])
        self.assertEqual(messages(report.warnings), [])
        counts = report.counts["docs/manual/01-links.md"]
        self.assertEqual((counts["mermaid"], counts["pseudocode"], counts["images"], counts["steps"]),
                         (1, 1, 1, 1))


class Errors(unittest.TestCase):
    def setUp(self):
        self.f = Fixture().good()

    def errors(self, **kw) -> list[str]:
        return messages(self.f.run(**kw).errors)

    def test_missing_image(self):
        self.f.write("docs/manual/01-links.md", GOOD_CHAPTER.replace("links.png", "nope.png"))
        self.assertIn("docs/manual/01-links.md: image images/nope.png does not exist", self.errors())

    def test_image_without_alt(self):
        self.f.write("docs/manual/01-links.md", GOOD_CHAPTER.replace("[Typing a link, with a match offered.]", "[]"))
        self.assertIn("docs/manual/01-links.md: image images/links.png has no alt text", self.errors())

    def test_html_image_without_alt(self):
        self.f.write("README.md", README.replace(' alt="The main screen."', ""))
        self.assertTrue(any("hero.png has no alt text" in e for e in self.errors()))

    def test_link_to_a_missing_heading_in_another_page(self):
        self.f.write("docs/manual/01-links.md", GOOD_CHAPTER.replace("#find-a-note", "#nowhere"))
        self.assertIn("docs/manual/01-links.md: link to 02-search.md#nowhere: no such heading there",
                      self.errors())

    def test_link_row_anchor_that_is_not_a_heading(self):
        self.f.write("README.md", README.replace("#development", "#developing"))
        self.assertIn("README.md: link to #developing: no such heading on this page", self.errors())

    def test_link_to_a_missing_file(self):
        self.f.write("docs/manual/01-links.md", GOOD_CHAPTER.replace("02-search.md#find-a-note", "09-gone.md"))
        self.assertIn("docs/manual/01-links.md: link to 09-gone.md: no such file", self.errors())

    def test_links_inside_code_are_not_checked(self):
        self.f.write("docs/manual/01-links.md", GOOD_CHAPTER + "\n```markdown\n[x](missing.md)\n```\n")
        self.assertEqual(self.errors(), [])

    def test_chapter_without_a_diagram(self):
        text = GOOD_CHAPTER.split("```mermaid")[0] + GOOD_CHAPTER.split("```\n", 1)[1]
        self.f.write("docs/manual/01-links.md", text)
        self.assertIn("docs/manual/01-links.md: no Mermaid diagram", self.errors())

    def test_unknown_or_broken_mermaid(self):
        self.f.write("docs/manual/01-links.md", GOOD_CHAPTER.replace("flowchart LR", "flowchat LR"))
        self.assertTrue(any("not a diagram type" in e for e in self.errors()))
        self.f.write("docs/manual/01-links.md", GOOD_CHAPTER.replace('A["Home"]', 'A["Home"'))
        self.assertTrue(any("unbalanced brackets" in e for e in self.errors()))

    def test_mermaid_front_matter_is_allowed(self):
        self.f.write("docs/manual/01-links.md", GOOD_CHAPTER.replace(
            "```mermaid\n", "```mermaid\n---\ntitle: Links\n---\n"))
        self.assertEqual(self.errors(), [])

    def test_chapter_missing_from_the_index(self):
        self.f.write("docs/manual/03-graph.md", GOOD_CHAPTER.replace("# Links", "# Graph"))
        self.assertIn("docs/manual/README.md: the index does not list 03-graph.md", self.errors())

    def test_chapter_without_a_screenshot(self):
        self.f.write("docs/manual/01-links.md",
                     GOOD_CHAPTER.replace("![Typing a link, with a match offered.](images/links.png)\n", ""))
        self.assertIn("docs/manual/01-links.md: no screenshot", self.errors())

    def test_readme_must_link_the_manual(self):
        self.f.write("README.md", README.replace("docs/manual/README.md", "elsewhere.md"))
        errors = self.errors()
        self.assertIn("README.md: the README does not link to the user manual in docs/manual/", errors)

    def test_screenshot_promised_but_not_taken(self):
        self.f.write("docs/screenshots.json",
                     '{"shots": [{"name": "graph", "out": "docs/manual/images/graph.png", "alt": "x", "path": "/"}]}')
        self.assertIn("docs/screenshots.json: shot 'graph' has not been taken: "
                      "docs/manual/images/graph.png is missing",
                      self.errors(plan="docs/screenshots.json"))


class Warnings(unittest.TestCase):
    def test_template_drift_is_a_warning_not_an_error(self):
        f = Fixture().good()
        bare = "# Links\n\nIntro.\n\n![A link.](images/links.png)\n\n```mermaid\nflowchart LR\n  A --> B\n```\n"
        f.write("docs/manual/01-links.md", bare)
        f.write("docs/manual/02-search.md", SEARCH_CHAPTER.replace("#make-a-link", ""))
        report = f.run()
        self.assertEqual(messages(report.errors), [])
        warned = " ".join(messages(report.warnings))
        for want in ("no '## How it works' section", "no pseudocode", "no numbered steps",
                     "no table", "no '## Tips' section", "no '## See also' section"):
            self.assertIn(want, warned)

    def test_file_trees_are_not_pseudocode(self):
        self.assertFalse(docs_check.looks_like_pseudocode("vault/\n├── a.md\n└── if-then.md\nfor\n"))
        self.assertTrue(docs_check.looks_like_pseudocode("for each note:\n  if linked\n    return\n"))

    def test_readme_without_kite_sections(self):
        f = Fixture()
        f.write("README.md", "# Demo\n\nSome words.\n")
        warned = " ".join(messages(f.run(manual=None).warnings))
        for want in ("no hero image", "no link row", "a Features section", "no 'Why <project>?'",
                     "no Mermaid diagram"):
            self.assertIn(want, warned)


class Cli(unittest.TestCase):
    def test_exit_code_follows_errors(self):
        f = Fixture().good()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(docs_check.main(["--root", f.root, "--readme", "README.md",
                                              "--manual", "docs/manual", "--json"]), 0)
            f.write("README.md", README.replace("hero.png", "gone.png", 1))
            self.assertEqual(docs_check.main(["--root", f.root, "--readme", "README.md"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
