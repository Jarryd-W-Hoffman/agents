#!/usr/bin/env python3
"""Check a README and a user manual against the Kite-shaped template, with no model.

    python3 docs_check.py [--root <dir>] [--readme README.md] [--manual docs/manual]
                          [--plan docs/screenshots.json] [--json]

Errors are things a reader would trip over: an image that does not exist or
has no alt text, a link to a page or heading that is not there, an empty or
unknown Mermaid diagram, a manual chapter without its "How it works" diagram,
a chapter the manual's index does not list, a screenshot the plan promises
but nobody took. Warnings are template drift: a chapter with no pseudocode,
no numbered steps, no Tips or See also, a README without a hero image or a
link row.

Exits 1 when there are errors, 0 otherwise. Prints a short report, or the
whole result as JSON with --json.

Standard library only; runs on Python 3.9.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from urllib.parse import unquote

MERMAID_TYPES = (
    "flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram", "stateDiagram-v2",
    "erDiagram", "journey", "gantt", "pie", "quadrantChart", "requirementDiagram", "gitGraph",
    "mindmap", "timeline", "sankey-beta", "xychart-beta", "block-beta", "packet-beta",
    "architecture-beta", "kanban", "C4Context", "C4Container", "C4Component", "C4Dynamic",
    "radar-beta", "treemap-beta",
)
CHAPTER_NAME = re.compile(r"^\d{2}-[a-z0-9-]+\.md$")
FENCE = re.compile(r"^(```+|~~~+)\s*([\w+-]*)[^\n]*\n(.*?)^\1\s*$", re.M | re.S)
MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_IMAGE = re.compile(r"<img\b([^>]*)>", re.I)
MD_LINK = re.compile(r"(?<!!)\[(?:[^\]\[]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_LINK = re.compile(r"<a\b[^>]*\bhref=\"([^\"]+)\"", re.I)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.M)
EXPLICIT_ANCHOR = re.compile(r"<a\s+(?:name|id)=\"([^\"]+)\"", re.I)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def strip_code(text: str) -> str:
    """The text with fenced blocks and inline code blanked, line numbers kept."""
    text = FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return re.sub(r"`[^`\n]+`", "``", text)


def slug(heading: str) -> str:
    """GitHub's heading anchor: lowercase, punctuation and emoji dropped, spaces to hyphens."""
    text = re.sub(r"<[^>]+>", "", heading)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "").strip().lower()
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if ch in ("-", "_") or cat[0] in ("L", "N") or cat == "Mn":
            out.append(ch)
        elif ch == " ":
            out.append("-")
    return "".join(out)


def anchors(text: str) -> set[str]:
    seen: dict[str, int] = {}
    out = set(EXPLICIT_ANCHOR.findall(text))
    for _, title in HEADING.findall(strip_code(text)):
        base = slug(title)
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.add(base if n == 0 else f"{base}-{n}")
    return out


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


class Report:
    def __init__(self, root: str):
        self.root = root
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.counts: dict[str, dict] = {}

    def error(self, path: str, line: int, message: str) -> None:
        self.errors.append({"path": path, "line": line, "message": message})

    def warn(self, path: str, line: int, message: str) -> None:
        self.warnings.append({"path": path, "line": line, "message": message})

    def as_dict(self) -> dict:
        return {"ok": not self.errors, "errors": self.errors, "warnings": self.warnings,
                "pages": self.counts}


# --------------------------------------------------------------------------
# Checks common to every page
# --------------------------------------------------------------------------

def check_page(report: Report, rel: str, anchor_cache: dict[str, set[str]]) -> dict:
    path = os.path.join(report.root, rel)
    text = read(path)
    prose = strip_code(text)
    here = os.path.dirname(path)
    counts = {"images": 0, "mermaid": 0, "pseudocode": 0, "code": 0, "tables": 0, "steps": 0}

    for m in MD_IMAGE.finditer(prose):
        counts["images"] += 1
        alt, src = m.group(1), m.group(2)
        check_image(report, rel, line_of(prose, m.start()), here, src, alt)
    for m in HTML_IMAGE.finditer(prose):
        counts["images"] += 1
        attrs = m.group(1)
        src = re.search(r"\bsrc=\"([^\"]+)\"", attrs)
        alt = re.search(r"\balt=\"([^\"]*)\"", attrs)
        if src:
            check_image(report, rel, line_of(prose, m.start()), here, src.group(1),
                        alt.group(1) if alt else "")

    for m in list(MD_LINK.finditer(prose)) + list(HTML_LINK.finditer(prose)):
        check_link(report, rel, line_of(prose, m.start()), here, m.group(1), text, anchor_cache)

    for m in FENCE.finditer(text):
        lang, body = m.group(2), m.group(3)
        line = line_of(text, m.start())
        if lang == "mermaid":
            counts["mermaid"] += 1
            check_mermaid(report, rel, line, body)
        elif lang in ("text", "pseudo", "pseudocode", "") and looks_like_pseudocode(body):
            counts["pseudocode"] += 1
        else:
            counts["code"] += 1

    counts["tables"] = len(re.findall(r"^\|[ :-]*-{3,}[ :|-]*\|\s*$", prose, re.M))
    counts["steps"] = len(re.findall(r"^1\.\s", prose, re.M))
    report.counts[rel] = counts
    return {"text": text, "prose": prose, "counts": counts}


def check_image(report: Report, rel: str, line: int, here: str, src: str, alt: str) -> None:
    if not alt.strip():
        report.error(rel, line, f"image {src} has no alt text")
    if re.match(r"^(https?:)?//", src) or src.startswith("data:"):
        return
    target = os.path.normpath(os.path.join(here, unquote(src.split("#")[0].split("?")[0])))
    if not os.path.isfile(target):
        report.error(rel, line, f"image {src} does not exist")


def check_link(report: Report, rel: str, line: int, here: str, href: str, text: str,
               anchor_cache: dict[str, set[str]]) -> None:
    if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):
        return  # http:, https:, mailto: and friends are not checked offline
    target, _, fragment = href.partition("#")
    if not target:
        if fragment and fragment.lower() not in anchor_cache.setdefault(rel, anchors(text)):
            report.error(rel, line, f"link to #{fragment}: no such heading on this page")
        return
    full = os.path.normpath(os.path.join(here, unquote(target)))
    if not os.path.exists(full):
        report.error(rel, line, f"link to {target}: no such file")
        return
    if fragment and full.endswith(".md") and os.path.isfile(full):
        key = os.path.relpath(full, report.root)
        if key not in anchor_cache:
            anchor_cache[key] = anchors(read(full))
        if fragment.lower() not in anchor_cache[key]:
            report.error(rel, line, f"link to {target}#{fragment}: no such heading there")


def check_mermaid(report: Report, rel: str, line: int, body: str) -> None:
    lines = [ln.strip() for ln in body.splitlines()
             if ln.strip() and not ln.strip().startswith("%%")]
    if lines and lines[0] == "---":  # front matter (title:, config:)
        try:
            lines = lines[lines.index("---", 1) + 1:]
        except ValueError:
            report.error(rel, line, "mermaid front matter is not closed with ---")
            return
    if not lines:
        report.error(rel, line, "mermaid diagram is empty")
        return
    kind = lines[0].split()[0]
    if kind not in MERMAID_TYPES:
        report.error(rel, line, f"mermaid diagram starts with '{kind}', not a diagram type")
        return
    if len(lines) < 2:
        report.error(rel, line, f"mermaid {kind} has nothing in it")
    opened = sum(ln.count("[") + ln.count("(") + ln.count("{") for ln in lines)
    closed = sum(ln.count("]") + ln.count(")") + ln.count("}") for ln in lines)
    if opened != closed:
        report.error(rel, line, f"mermaid {kind}: unbalanced brackets ({opened} open, {closed} close)")


def looks_like_pseudocode(body: str) -> bool:
    """A ```text block that reads like steps of an algorithm, not a file tree or output."""
    if re.search(r"[├└│]", body):
        return False
    words = r"\b(for each|for|if|else|when|while|return|then|repeat|until|otherwise|function|loop)\b"
    return len(re.findall(words, body, re.I)) >= 2 and body.count("\n") >= 2


# --------------------------------------------------------------------------
# README
# --------------------------------------------------------------------------

def check_readme(report: Report, rel: str, cache: dict[str, set[str]], manual: str | None) -> None:
    page = check_page(report, rel, cache)
    text, counts = page["text"], page["counts"]
    head = text[:4000]
    if not re.search(r"^<h1|^# ", text, re.M):
        report.error(rel, 1, "no title (# or <h1>)")
    if not (re.search(r"<img\b", head) or re.search(r"!\[", head)):
        report.warn(rel, 1, "no hero image near the top")
    if text.count("](#") + text.count('href="#') < 4:
        report.warn(rel, 1, "no link row to the sections (Kite has one under the hero)")
    headings = [t for _, t in HEADING.findall(page["prose"])]
    plain = [re.sub(r"[^\w ]", "", h).strip().lower() for h in headings]
    for want, why in (("features", "a Features section"),
                      ("development", "a Development section"),
                      ("license", "a License section")):
        if not any(want in h or (want == "license" and "licence" in h) for h in plain):
            report.warn(rel, 1, f"no {why}")
    if not any(h.startswith("why") for h in plain):
        report.warn(rel, 1, "no 'Why <project>?' section")
    if not any("built" in h or "how it works" in h or "architecture" in h for h in plain):
        report.warn(rel, 1, "no 'How it's built' or 'How it works' section")
    if counts["mermaid"] == 0:
        report.warn(rel, 1, "no Mermaid diagram")
    if counts["images"] < 2:
        report.warn(rel, 1, f"only {counts['images']} image(s); Kite pairs screenshots with each feature group")
    if manual and os.path.isdir(os.path.join(report.root, manual)):
        if manual.rstrip("/") + "/" not in text and manual.rstrip("/") not in text:
            report.error(rel, 1, f"the README does not link to the user manual in {manual}/")


# --------------------------------------------------------------------------
# Manual
# --------------------------------------------------------------------------

def check_manual(report: Report, manual: str, cache: dict[str, set[str]]) -> None:
    folder = os.path.join(report.root, manual)
    if not os.path.isdir(folder):
        report.error(manual, 0, "manual directory does not exist")
        return
    index = os.path.join(manual, "README.md")
    names = sorted(os.listdir(folder))
    chapters = [n for n in names if CHAPTER_NAME.match(n)]
    strays = [n for n in names if n.endswith(".md") and n != "README.md" and n not in chapters]
    for n in strays:
        report.warn(os.path.join(manual, n), 1, "not named NN-topic.md, so it sorts out of order")
    if not chapters:
        report.error(manual, 0, "no chapters (NN-topic.md)")
    numbers = [int(n[:2]) for n in chapters]
    if numbers and numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        report.warn(manual, 0, f"chapter numbers have gaps or repeats: {numbers}")

    if not os.path.isfile(os.path.join(report.root, index)):
        report.error(index, 0, "the manual has no README.md index")
    else:
        page = check_page(report, index, cache)
        for n in chapters:
            if f"]({n})" not in page["text"] and f"({n}#" not in page["text"]:
                report.error(index, 1, f"the index does not list {n}")
        if "conventions" not in page["text"].lower():
            report.warn(index, 1, "no Conventions section")
        if "screenshot" not in page["text"].lower():
            report.warn(index, 1, "no 'About the screenshots' note saying how to retake them")

    for i, n in enumerate(chapters):
        rel = os.path.join(manual, n)
        page = check_page(report, rel, cache)
        text, prose, counts = page["text"], page["prose"], page["counts"]
        if not re.match(r"^# \S", text):
            report.error(rel, 1, "does not start with a # title")
        sections = {slug(t): (line_of(prose, m.start()), m) for m in HEADING.finditer(prose)
                    for _, t in [m.groups()] if m.group(1) == "##"}
        # Kite titles it "How it works", or "How tags work" when the chapter has several.
        how = re.search(r"^## How [^\n]*\bworks?\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
        if counts["mermaid"] == 0:
            report.error(rel, 1, "no Mermaid diagram")
        if not how:
            report.warn(rel, 1, "no '## How it works' section")
        elif "```mermaid" not in how.group(1):
            report.warn(rel, line_of(text, how.start()), "'How it works' has no Mermaid diagram")
        if counts["images"] == 0:
            report.error(rel, 1, "no screenshot")
        if counts["pseudocode"] == 0:
            report.warn(rel, 1, "no pseudocode (a ```text block of the steps the feature takes)")
        if counts["steps"] == 0:
            report.warn(rel, 1, "no numbered steps")
        if counts["tables"] == 0:
            report.warn(rel, 1, "no table")
        if "tips" not in sections:
            report.warn(rel, 1, "no '## Tips' section")
        if "see-also" not in sections:
            report.warn(rel, 1, "no '## See also' section")
        elif i > 0 or len(chapters) > 1:
            see_also = text[text.find("## See also"):]
            if not re.search(r"\]\(\d{2}-[a-z0-9-]+\.md", see_also):
                report.warn(rel, 1, "'See also' links to no other chapter")


def check_plan(report: Report, plan: str) -> None:
    path = os.path.join(report.root, plan)
    try:
        data = json.loads(read(path))
    except (OSError, ValueError) as exc:
        report.error(plan, 0, f"cannot read the screenshot plan: {exc}")
        return
    for i, shot in enumerate(data.get("shots", [])):
        out = shot.get("out") if isinstance(shot, dict) else None
        if not out:
            report.error(plan, 0, f"shot {i} has no 'out'")
        elif not os.path.isfile(os.path.join(report.root, out)):
            report.error(plan, 0, f"shot '{shot.get('name', i)}' has not been taken: {out} is missing")


def run(root: str, readme: str | None, manual: str | None, plan: str | None) -> Report:
    report = Report(os.path.abspath(root))
    cache: dict[str, set[str]] = {}
    if readme:
        if os.path.isfile(os.path.join(report.root, readme)):
            check_readme(report, readme, cache, manual)
        else:
            report.error(readme, 0, "does not exist")
    if manual:
        check_manual(report, manual.rstrip("/"), cache)
    if plan and os.path.isfile(os.path.join(report.root, plan)):
        check_plan(report, plan)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--readme", default=None, help="README to check, relative to --root")
    ap.add_argument("--manual", default=None, help="manual directory, relative to --root")
    ap.add_argument("--plan", default=None, help="screenshot plan, relative to --root")
    ap.add_argument("--json", action="store_true", help="print the whole result as JSON")
    args = ap.parse_args(argv)
    if not (args.readme or args.manual or args.plan):
        args.readme = "README.md"
    report = run(args.root, args.readme, args.manual, args.plan)
    if args.json:
        json.dump(report.as_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for kind, items in (("error", report.errors), ("warning", report.warnings)):
            for item in items:
                print(f"{item['path']}:{item['line']}: {kind}: {item['message']}")
        print(f"docs-check: {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
