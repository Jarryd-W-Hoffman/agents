#!/usr/bin/env python3
"""Merge what the selected plugins reported into one result, without a model.

The lead runs the plan, launches one subagent per selected plugin, and
writes down what each came back with in a results file. This script turns
that into one findings list and one verdict, by rules rather than judgement:

- A plugin's findings.json must satisfy the finding contract, and every
  finding's ID prefix must be one the registry gives that plugin. A file that
  breaks either is not that plugin's report, and the plugin counts as failed.
- A selected plugin that did not report, for any reason, makes the verdict
  INCOMPLETE. A review that did not happen is not a clean one.
- Findings from different plugins are kept as they are, never merged. Two
  plugins answer different questions, and only a person can say two findings
  are the same problem. Findings on the same file with overlapping lines are
  listed as overlaps for that person.

Results file (written by the lead):

    {
      "target": "PR #214: Add currency to orders",
      "plan": { ...plan.py output... },
      "results": {
        "fourpass": {"status": "reported", "findings": "/tmp/a/findings.json"},
        "migrations": {"status": "nothing_to_do", "reason": "no migrations"},
        "impact":    {"status": "reported", "impact": "/tmp/c/impact.json"},
        "<plugin>":         {"status": "not_installed" | "failed", "reason": "..."}
      }
    }

    merge.py results.json --out-dir <dir>

writes <dir>/findings.json (the merged list, validated) and <dir>/summary.json
(the verdict, each plugin's status and counts, overlaps, and the impact map's
headline numbers), and prints summary.json.

Standard library only; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from finding_contract import validate as validate_findings  # noqa: E402

REGISTRY = os.path.join(os.path.dirname(HERE), "registry.json")
STATUSES = ("reported", "nothing_to_do", "not_installed", "failed")
SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2}
IMPACT_KEYS = ("changed", "callers", "entry_points", "tests", "limits")


def verdict_for(findings: list[dict]) -> str:
    severities = {f["severity"] for f in findings}
    if "critical" in severities:
        return "FAIL"
    if "major" in severities:
        return "REQUEST_CHANGES"
    if "minor" in severities:
        return "PASS_WITH_NOTES"
    return "PASS"


def _load(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _span(f: dict) -> tuple[int, int]:
    return f["line"], f.get("end_line", f["line"])


def overlaps(findings: list[dict], owner: dict[str, str]) -> list[dict]:
    """Pairs of findings from different plugins on the same file and overlapping lines."""
    out = []
    for i, a in enumerate(findings):
        for b in findings[i + 1:]:
            if owner[a["id"]] == owner[b["id"]] or a["path"] != b["path"]:
                continue
            (a0, a1), (b0, b1) = _span(a), _span(b)
            if a0 <= b1 and b0 <= a1:
                out.append({"ids": [a["id"], b["id"]], "path": a["path"],
                            "lines": [max(a0, b0), min(a1, b1)]})
    return out


def merge(results: dict, registry: dict) -> tuple[list[dict], dict]:
    entries = {p["name"]: p for p in registry["plugins"]}
    plan = results.get("plan") or {}
    selected = [s["plugin"] for s in plan.get("selected", [])]
    reported = results.get("results") or {}
    plugins, merged, owner, impact = [], [], {}, None

    for name in selected:
        r = dict(reported.get(name) or {"status": "failed", "reason": "no result recorded for a selected plugin"})
        status = r.get("status")
        row = {"plugin": name, "status": status, "reason": r.get("reason", ""), "note": r.get("note", ""),
               "counts": {"critical": 0, "major": 0, "minor": 0}, "files": []}
        if status not in STATUSES:
            row.update(status="failed", reason=f"unknown status {status!r}")
        elif status == "reported":
            output = entries.get(name, {}).get("output")
            if output == "findings":
                path = r.get("findings")
                problem, findings = None, []
                if not path or not os.path.isfile(path):
                    problem = f"findings.json not found at {path!r}"
                else:
                    try:
                        findings = _load(path)
                    except (OSError, json.JSONDecodeError) as exc:
                        problem = f"findings.json unreadable: {exc}"
                if problem is None:
                    errors = validate_findings(findings)
                    if errors:
                        problem = f"findings.json breaks the finding contract: {errors[0]}"
                if problem is None:
                    owned = set(entries[name].get("prefixes", []))
                    stray = sorted({f["id"].split("-")[0] for f in findings} - owned)
                    if stray:
                        problem = (f"findings use prefixes {stray} that the registry does not give "
                                   f"{name} ({sorted(owned)})")
                if problem:
                    row.update(status="failed", reason=problem)
                else:
                    row["files"].append(path)
                    for f in findings:
                        row["counts"][f["severity"]] += 1
                        owner[f["id"]] = name
                    merged.extend(findings)
            elif output == "impact":
                path = r.get("impact")
                try:
                    data = _load(path) if path else None
                except (OSError, json.JSONDecodeError):
                    data = None
                if not isinstance(data, dict) or any(k not in data for k in IMPACT_KEYS):
                    row.update(status="failed", reason=f"impact.json missing or not an impact map at {path!r}")
                else:
                    row["files"].append(path)
                    impact = {"plugin": name, "path": path, "mode": data.get("mode"),
                              "changed": len(data["changed"]), "entry_points": len(data["entry_points"]),
                              "callers": len(data["callers"]),
                              "uncovered": len(data["tests"].get("uncovered", [])),
                              "risks": len(data.get("risks", []))}
            else:
                row.update(status="failed", reason=f"registry gives {name} no readable output ({output!r})")
        for key in ("report", "markdown"):
            if r.get(key):
                row["files"].append(r[key])
        plugins.append(row)

    # IDs are unique per plugin by contract, and prefixes are unique per
    # plugin by registry, so the merged list keeps every ID as it was.
    merged.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], -f["confidence"], f["path"], f["line"]))
    missing = [p for p in plugins if p["status"] not in ("reported", "nothing_to_do")]
    verdict = "INCOMPLETE" if missing else verdict_for(merged)
    summary = {
        "target": results.get("target", ""),
        "verdict": verdict,
        "incomplete_because": [f"{p['plugin']}: {p['status']}"
                               + (f" ({p['reason']})" if p["reason"] else "") for p in missing],
        "findings_verdict": verdict_for(merged),
        "plugins": plugins,
        "counts": {s: sum(p["counts"][s] for p in plugins) for s in ("critical", "major", "minor")},
        "overlaps": overlaps(merged, owner),
        "impact": impact,
        "follow_ups": plan.get("follow_ups", []),
        "skipped": plan.get("skipped", []),
    }
    return merged, summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("results", help="the results file the lead wrote")
    ap.add_argument("--out-dir", required=True, help="where to write findings.json and summary.json")
    ap.add_argument("--registry", default=REGISTRY, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        results, registry = _load(args.results), _load(args.registry)
        merged, summary = merge(results, registry)
        errors = validate_findings(merged)
        if errors:
            raise ValueError("merged findings break the finding contract: " + "; ".join(errors))
        os.makedirs(args.out_dir, exist_ok=True)
        with open(os.path.join(args.out_dir, "findings.json"), "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2)
            fh.write("\n")
        with open(os.path.join(args.out_dir, "summary.json"), "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
            fh.write("\n")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"merge: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
