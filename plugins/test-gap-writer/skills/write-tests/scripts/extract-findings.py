#!/usr/bin/env python3
"""Turn a four-pass review report into a findings list the test writers can act on.

Reads the merged report that four-pass-review's `review` skill writes (see its
`references/report-template.md`) and emits one JSON object per finding in the
finding contract this plugin shares with that one:

    id, title, severity, confidence, pass, path, line, [end_line], body, [fix]

Usage:
    extract-findings.py <report.md>                 # JSON to stdout
    extract-findings.py <report.md> --out <file>    # JSON to a file

Exits 1 with a message on stderr when the report contains no findings it can
parse, so the lead stops rather than launching writers with nothing to do, and
when what it parsed breaks the finding contract (finding.schema.json beside
this script), so a malformed report is refused rather than half-read.

Parsing the report is the fallback. four-pass-review saves a validated
findings.json next to its report.md, and the skill uses that when it exists;
the report's layout may change, the contract may not.

Two finding shapes exist in the report, and both are handled:

    ## Critical (1)                      ## Minor (1)
    ### [COR-1] Title                    - **[CNS-3]** `path:12` — desc (confidence 82, consistency)
    `path:7` · confidence 92 · correctness
    Body sentences.
    **Fix:** suggestion

A location may carry a range, `path:7-12`, which becomes `end_line`. The
pass may be followed by ", also raised by <pass>", which is kept out of `pass`.

Standard library only; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# The finding contract sits beside this script. Nothing puts this directory on
# sys.path when the script is run by absolute path or loaded by the tests.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from finding_contract import validate as validate_findings  # noqa: E402

SEVERITY_SECTIONS = {"critical": "critical", "major": "major", "minor": "minor"}
# A pass name as the contract spells it: lower-case, hyphens allowed, so a
# plugin's pass such as `migration-safety` parses as well as the four.
PASS = r"[a-z][a-z0-9-]*"

# `## Critical (2)` -- the count is optional so a hand-written report still parses.
SECTION_RE = re.compile(r"^##\s+(Critical|Major|Minor)\b", re.I)
# Any other `## …` heading closes the findings section we were in.
OTHER_SECTION_RE = re.compile(r"^##\s+")
# `### [COR-1] Title of the finding`
HEADING_RE = re.compile(r"^###\s+\[([A-Z]+-\d+)\]\s+(.+?)\s*$")
# `` `path/to/file.py:7` · confidence 92 · correctness, also raised by completeness ``
# The separator is whatever the template used: a middle dot or a plain hyphen.
LOCATION_RE = re.compile(
    r"^`(?P<path>[^`:]+):(?P<line>\d+)(?:-(?P<end>\d+))?`"
    r"\s*[·\-–—]\s*confidence\s+(?P<conf>\d+)"
    r"\s*[·\-–—]\s*(?P<pass>" + PASS + r")"
)
FIX_RE = re.compile(r"^\*\*Fix:\*\*\s*(.*)$")
# `- **[CNS-3]** `path:12` — one-line description (confidence 82, consistency)`
BULLET_RE = re.compile(
    r"^-\s+\*\*\[(?P<id>[A-Z]+-\d+)\]\*\*\s+"
    r"`(?P<path>[^`:]+):(?P<line>\d+)(?:-(?P<end>\d+))?`"
    r"\s*[·\-–—]\s*(?P<desc>.+?)"
    r"\s*\(confidence\s+(?P<conf>\d+),\s*(?P<pass>" + PASS + r")[^)]*\)\s*$"
)


def _finding(id_: str, title: str, severity: str, confidence: int, pass_: str,
             path: str, line: int, end_line, body: str, fix) -> dict:
    out = {
        "id": id_,
        "title": title,
        "severity": severity,
        "confidence": confidence,
        "pass": pass_,
        "path": path,
        "line": line,
        "body": body,
    }
    if end_line is not None:
        out["end_line"] = end_line
    if fix:
        out["fix"] = fix
    return out


def parse_report(text: str) -> list[dict]:
    """Parse a merged four-pass report into finding-contract dicts, in document order."""
    findings: list[dict] = []
    severity = None  # the ## section we are inside, if it is a severity section
    current = None   # the ### finding being accumulated, as a mutable dict
    body_lines: list[str] = []

    def flush():
        nonlocal current, body_lines
        if current is None:
            return
        if current.get("path") is not None:
            # The contract requires a body. A heading with only a location and
            # a fix line still names the defect, in its title.
            body = " ".join(l.strip() for l in body_lines if l.strip()) or current["title"]
            findings.append(_finding(
                current["id"], current["title"], current["severity"],
                current["confidence"], current["pass"], current["path"],
                current["line"], current.get("end_line"), body, current.get("fix"),
            ))
        current = None
        body_lines = []

    for raw in text.splitlines():
        line = raw.rstrip()

        m = SECTION_RE.match(line)
        if m:
            flush()
            severity = SEVERITY_SECTIONS[m.group(1).lower()]
            continue
        if OTHER_SECTION_RE.match(line):
            flush()
            severity = None
            continue
        if severity is None:
            continue

        m = HEADING_RE.match(line)
        if m:
            flush()
            current = {"id": m.group(1), "title": m.group(2), "severity": severity}
            continue

        m = BULLET_RE.match(line)
        if m:
            flush()
            findings.append(_finding(
                m.group("id"), m.group("desc"), severity, int(m.group("conf")),
                m.group("pass"), m.group("path"), int(m.group("line")),
                int(m.group("end")) if m.group("end") else None, m.group("desc"), None,
            ))
            continue

        if current is None:
            continue

        m = LOCATION_RE.match(line)
        if m and current.get("path") is None:
            current["path"] = m.group("path")
            current["line"] = int(m.group("line"))
            current["end_line"] = int(m.group("end")) if m.group("end") else None
            current["confidence"] = int(m.group("conf"))
            current["pass"] = m.group("pass")
            continue

        m = FIX_RE.match(line)
        if m:
            current["fix"] = m.group(1).strip()
            continue

        body_lines.append(line)

    flush()
    return findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("report", help="path to the merged four-pass report (markdown)")
    ap.add_argument("--out", help="write JSON here instead of stdout")
    args = ap.parse_args(argv)

    try:
        with open(args.report, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"extract-findings: cannot read {args.report}: {exc}", file=sys.stderr)
        return 1

    findings = parse_report(text)
    if not findings:
        print("extract-findings: no findings parsed. Expected `### [ID] title` blocks under "
              "## Critical / ## Major, or `- **[ID]** ...` bullets under ## Minor, as the "
              "four-pass-review report template writes them.", file=sys.stderr)
        return 1

    errors = validate_findings(findings)
    if errors:
        for e in errors:
            print(f"extract-findings: {e}", file=sys.stderr)
        print("extract-findings: the parsed findings break the finding contract "
              "(finding.schema.json); fix the report or pass a findings.json", file=sys.stderr)
        return 1

    payload = json.dumps(findings, indent=2) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
        print(f"extract-findings: {len(findings)} finding(s) -> {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
