#!/usr/bin/env python3
"""Tests for skills/review/scripts/merge.py. Run: python3 tests/test_merge.py"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "skills", "review", "scripts")
spec = importlib.util.spec_from_file_location("merge", os.path.join(SCRIPTS, "merge.py"))
merge_mod = importlib.util.module_from_spec(spec)
sys.modules["merge"] = merge_mod
spec.loader.exec_module(merge_mod)  # type: ignore[union-attr]

with open(os.path.join(REPO, "skills", "review", "registry.json"), encoding="utf-8") as fh:
    REGISTRY = json.load(fh)


def finding(fid, severity="major", path="app/Order.php", line=10, **kw):
    f = {"id": fid, "title": "t", "severity": severity, "confidence": 85,
         "pass": "migration-safety" if fid.startswith("MIG") else "correctness",
         "path": path, "line": line, "body": "b"}
    f.update(kw)
    return f


IMPACT = {"version": 1, "target": "t", "base": "b", "head": "h", "mode": "full",
          "changed": [{"symbol": "Order", "kind": "class", "change": "modified", "path": "app/Order.php", "line": 1}],
          "callers": [], "entry_points": [{"kind": "http", "name": "GET /orders", "path": "routes/web.php",
                                           "line": 3, "reaches": ["Order"]}],
          "tests": {"covering": [], "uncovered": ["Order"]}, "data": [], "contracts": [],
          "risks": [], "limits": ["l"]}


class Merge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name, data):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return path

    def results(self, selected, results):
        return {"target": "PR #1", "plan": {"selected": [{"plugin": p} for p in selected],
                                            "follow_ups": [{"plugin": "test-gap-writer"}], "skipped": []},
                "results": results}

    def run_merge(self, selected, results):
        return merge_mod.merge(self.results(selected, results), REGISTRY)

    def test_everything_reported(self):
        four = self.write("four.json", [finding("COR-1", "critical", line=12), finding("CNS-1", "minor")])
        mig = self.write("mig.json", [finding("MIG-1", "major", path="database/migrations/x.php")])
        imp = self.write("impact.json", IMPACT)
        merged, s = self.run_merge(
            ["four-pass-review", "migration-safety", "change-impact"],
            {"four-pass-review": {"status": "reported", "findings": four},
             "migration-safety": {"status": "reported", "findings": mig},
             "change-impact": {"status": "reported", "impact": imp}})
        self.assertEqual(s["verdict"], "FAIL")
        self.assertEqual([f["id"] for f in merged], ["COR-1", "MIG-1", "CNS-1"])
        self.assertEqual(s["counts"], {"critical": 1, "major": 1, "minor": 1})
        self.assertEqual((s["impact"]["entry_points"], s["impact"]["uncovered"]), (1, 1))
        self.assertEqual(s["follow_ups"], [{"plugin": "test-gap-writer"}])

    def test_verdict_scale(self):
        for severities, want in (([], "PASS"), (["minor"], "PASS_WITH_NOTES"),
                                 (["minor", "major"], "REQUEST_CHANGES"), (["critical"], "FAIL")):
            fs = [finding(f"COR-{i}", s) for i, s in enumerate(severities, 1)]
            self.assertEqual(merge_mod.verdict_for(fs), want)

    def test_missing_result_is_incomplete_not_clean(self):
        four = self.write("four.json", [])
        _, s = self.run_merge(["four-pass-review", "migration-safety"],
                              {"four-pass-review": {"status": "reported", "findings": four}})
        self.assertEqual(s["verdict"], "INCOMPLETE")
        self.assertEqual(s["findings_verdict"], "PASS")
        self.assertIn("migration-safety: failed (no result recorded", s["incomplete_because"][0])

    def test_not_installed_is_incomplete(self):
        four = self.write("four.json", [])
        _, s = self.run_merge(["four-pass-review", "migration-safety"],
                              {"four-pass-review": {"status": "reported", "findings": four},
                               "migration-safety": {"status": "not_installed"}})
        self.assertEqual(s["verdict"], "INCOMPLETE")

    def test_nothing_to_do_counts_as_reported(self):
        # migration-safety's own detector can find no migration the registry's
        # coarse patterns let through; that is a result, not a gap.
        four = self.write("four.json", [finding("CNS-1", "minor")])
        _, s = self.run_merge(["four-pass-review", "migration-safety"],
                              {"four-pass-review": {"status": "reported", "findings": four},
                               "migration-safety": {"status": "nothing_to_do", "reason": "no migrations"}})
        self.assertEqual(s["verdict"], "PASS_WITH_NOTES")

    def test_findings_breaking_the_contract_fail_the_plugin(self):
        bad = self.write("bad.json", [{"id": "COR-1", "title": "t"}])
        _, s = self.run_merge(["four-pass-review"], {"four-pass-review": {"status": "reported", "findings": bad}})
        self.assertEqual(s["plugins"][0]["status"], "failed")
        self.assertIn("finding contract", s["plugins"][0]["reason"])
        self.assertEqual(s["verdict"], "INCOMPLETE")

    def test_findings_with_a_foreign_prefix_fail_the_plugin(self):
        stolen = self.write("stolen.json", [finding("COR-1")])
        merged, s = self.run_merge(["migration-safety"],
                                   {"migration-safety": {"status": "reported", "findings": stolen}})
        self.assertEqual(merged, [])
        self.assertIn("prefixes ['COR']", s["plugins"][0]["reason"])

    def test_missing_or_unreadable_files_fail_the_plugin(self):
        broken = os.path.join(self.tmp, "broken.json")
        with open(broken, "w") as fh:
            fh.write("[{")
        for path in (os.path.join(self.tmp, "nope.json"), broken, None):
            _, s = self.run_merge(["four-pass-review"],
                                  {"four-pass-review": {"status": "reported", "findings": path}})
            self.assertEqual(s["plugins"][0]["status"], "failed", path)

    def test_impact_that_is_not_a_map_fails(self):
        _, s = self.run_merge(["change-impact"], {"change-impact": {"status": "reported",
                                                                    "impact": self.write("i.json", {"x": 1})}})
        self.assertEqual(s["plugins"][0]["status"], "failed")

    def test_a_note_never_changes_the_status(self):
        # Measured: a plugin saved valid findings but not its report.md, was
        # recorded failed, and a critical finding was dropped from the merge.
        mig = self.write("mig.json", [finding("MIG-1", "critical")])
        merged, s = self.run_merge(["migration-safety"], {"migration-safety": {
            "status": "reported", "findings": mig, "note": "report.md could not be saved"}})
        self.assertEqual((s["verdict"], [f["id"] for f in merged]), ("FAIL", ["MIG-1"]))
        self.assertEqual(s["plugins"][0]["note"], "report.md could not be saved")

    def test_unknown_status(self):
        _, s = self.run_merge(["four-pass-review"], {"four-pass-review": {"status": "done"}})
        self.assertIn("unknown status", s["plugins"][0]["reason"])

    def test_overlaps_across_plugins_are_flagged_not_merged(self):
        four = self.write("four.json", [finding("COR-1", path="database/migrations/x.php", line=12, end_line=14)])
        mig = self.write("mig.json", [finding("MIG-1", path="database/migrations/x.php", line=14),
                                      finding("MIG-2", path="database/migrations/x.php", line=30)])
        merged, s = self.run_merge(["four-pass-review", "migration-safety"],
                                   {"four-pass-review": {"status": "reported", "findings": four},
                                    "migration-safety": {"status": "reported", "findings": mig}})
        self.assertEqual(len(merged), 3)
        self.assertEqual(s["overlaps"], [{"ids": ["COR-1", "MIG-1"], "path": "database/migrations/x.php",
                                          "lines": [14, 14]}])

    def test_same_plugin_findings_are_not_overlaps(self):
        four = self.write("four.json", [finding("COR-1", line=5), finding("CNS-1", line=5)])
        _, s = self.run_merge(["four-pass-review"], {"four-pass-review": {"status": "reported", "findings": four}})
        self.assertEqual(s["overlaps"], [])

    def test_unselected_results_are_ignored(self):
        # Only the plan's selection counts; a stray result cannot add findings.
        mig = self.write("mig.json", [finding("MIG-1")])
        merged, s = self.run_merge([], {"migration-safety": {"status": "reported", "findings": mig}})
        self.assertEqual((merged, s["verdict"]), ([], "PASS"))


class Cli(unittest.TestCase):
    def test_writes_both_files_and_the_merged_list_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            four = os.path.join(tmp, "four.json")
            with open(four, "w") as fh:
                json.dump([finding("COR-1")], fh)
            results = os.path.join(tmp, "results.json")
            with open(results, "w") as fh:
                json.dump({"target": "t", "plan": {"selected": [{"plugin": "four-pass-review"}]},
                           "results": {"four-pass-review": {"status": "reported", "findings": four}}}, fh)
            out = os.path.join(tmp, "out")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(merge_mod.main([results, "--out-dir", out]), 0)
            with open(os.path.join(out, "findings.json")) as fh:
                self.assertEqual(merge_mod.validate_findings(json.load(fh)), [])
            with open(os.path.join(out, "summary.json")) as fh:
                self.assertEqual(json.load(fh)["verdict"], "REQUEST_CHANGES")

    def test_unreadable_results_exit_1(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(merge_mod.main(["/nonexistent.json", "--out-dir", "/tmp/x"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
