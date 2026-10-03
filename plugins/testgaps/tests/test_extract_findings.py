#!/usr/bin/env python3
"""Tests for skills/write/scripts/extract-findings.py. Run: python3 tests/test_extract_findings.py"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "skills", "write", "scripts", "extract-findings.py")
spec = importlib.util.spec_from_file_location("extract_findings", SCRIPT)
ef = importlib.util.module_from_spec(spec)
sys.modules["extract_findings"] = ef
spec.loader.exec_module(ef)  # type: ignore[union-attr]

CONTRACT_KEYS = {"id", "title", "severity", "confidence", "pass", "path", "line", "body"}
OPTIONAL_KEYS = {"end_line", "fix"}

REPORT = """# Four-pass review: PR #142: Add invoice export

**Verdict:** FAIL
**Scope:** 3 files, 41 changed lines (abc123 → def456)
**Passes:** completeness REQUEST_CHANGES · correctness FAIL · compliance PASS · consistency PASS_WITH_NOTES
**Threshold:** 80 · **Verified:** 1 borderline findings checked, 0 refuted

## Critical (1)

### [COR-1] `export_row` dereferences `invoice.customer.email` when `customer` is nullable
`billing/exporter.py:7` · confidence 92 · correctness
API-created invoices have no customer, so export raises AttributeError
and the whole batch fails.
**Fix:** guard the None case and emit an empty email column.

## Major (2)

### [CMP-1] No tests cover the new export module
`billing/exporter.py:1-12` · confidence 85 · completeness, also raised by consistency
The change adds `export_row` and `export_all` with no test file; the repo tests every module under `billing/`.
**Fix:** add `tests/billing/test_exporter.py`.

### [CMP-2] Call site still uses the old name
`billing/report.py:30` · confidence 88 · completeness
`compute_total` was renamed but this caller was not updated.

## Minor (1)

- **[CNS-3]** `billing/exporter.py:3` — module docstring style differs from siblings (confidence 82, consistency)

## Pass summaries

- **Completeness:** One missing test file and one stale call site.
- **Correctness:** One null dereference.
- **Compliance:** No rule violations; consulted CLAUDE.md.
- **Consistency:** One docstring nit.

## Notes

- `### [NOT-1] This is not a finding` because it is under Notes, not a severity section.
"""


class ParseReport(unittest.TestCase):
    def setUp(self):
        self.findings = ef.parse_report(REPORT)
        self.by_id = {f["id"]: f for f in self.findings}

    def test_parses_every_finding_in_document_order(self):
        self.assertEqual([f["id"] for f in self.findings], ["COR-1", "CMP-1", "CMP-2", "CNS-3"])

    def test_headings_outside_severity_sections_are_ignored(self):
        self.assertNotIn("NOT-1", self.by_id)

    def test_output_keys_match_the_contract(self):
        for f in self.findings:
            with self.subTest(id=f["id"]):
                keys = set(f)
                self.assertTrue(CONTRACT_KEYS <= keys, f"missing {CONTRACT_KEYS - keys}")
                self.assertTrue(keys <= CONTRACT_KEYS | OPTIONAL_KEYS, f"extra {keys - CONTRACT_KEYS - OPTIONAL_KEYS}")
                self.assertIsInstance(f["confidence"], int)
                self.assertIsInstance(f["line"], int)

    def test_output_satisfies_the_finding_contract(self):
        self.assertEqual(ef.validate_findings(self.findings), [])

    def test_severity_comes_from_the_section(self):
        self.assertEqual(self.by_id["COR-1"]["severity"], "critical")
        self.assertEqual(self.by_id["CMP-1"]["severity"], "major")
        self.assertEqual(self.by_id["CMP-2"]["severity"], "major")
        self.assertEqual(self.by_id["CNS-3"]["severity"], "minor")

    def test_heading_finding_fields(self):
        f = self.by_id["COR-1"]
        self.assertEqual(f["title"], "`export_row` dereferences `invoice.customer.email` when `customer` is nullable")
        self.assertEqual(f["path"], "billing/exporter.py")
        self.assertEqual(f["line"], 7)
        self.assertNotIn("end_line", f)
        self.assertEqual(f["confidence"], 92)
        self.assertEqual(f["pass"], "correctness")
        self.assertEqual(f["body"], "API-created invoices have no customer, so export raises AttributeError "
                                    "and the whole batch fails.")
        self.assertEqual(f["fix"], "guard the None case and emit an empty email column.")

    def test_line_range_becomes_end_line(self):
        f = self.by_id["CMP-1"]
        self.assertEqual(f["line"], 1)
        self.assertEqual(f["end_line"], 12)

    def test_also_raised_by_is_kept_out_of_pass(self):
        self.assertEqual(self.by_id["CMP-1"]["pass"], "completeness")

    def test_finding_without_fix_has_no_fix_key(self):
        self.assertNotIn("fix", self.by_id["CMP-2"])

    def test_minor_bullet_fields(self):
        f = self.by_id["CNS-3"]
        self.assertEqual(f["path"], "billing/exporter.py")
        self.assertEqual(f["line"], 3)
        self.assertEqual(f["confidence"], 82)
        self.assertEqual(f["pass"], "consistency")
        self.assertEqual(f["title"], "module docstring style differs from siblings")
        self.assertEqual(f["body"], f["title"])

    def test_minor_bullet_with_range_and_also_raised_by(self):
        text = "## Minor (1)\n\n- **[CNS-4]** `a/b.py:5-9` — thing (confidence 81, consistency, also raised by compliance)\n"
        (f,) = ef.parse_report(text)
        self.assertEqual((f["line"], f["end_line"], f["pass"]), (5, 9, "consistency"))

    def test_heading_without_location_line_is_dropped(self):
        text = "## Major (1)\n\n### [COR-9] Orphan\nNo location line here.\n"
        self.assertEqual(ef.parse_report(text), [])

    def test_section_without_count_still_parses(self):
        text = "## Major\n\n### [COR-2] T\n`x.py:1` · confidence 90 · correctness\nbody\n"
        (f,) = ef.parse_report(text)
        self.assertEqual((f["id"], f["severity"]), ("COR-2", "major"))

    def test_hyphenated_pass_parses(self):
        text = ("## Major (1)\n\n### [MIG-1] Drops a column still read\n"
                "`database/migrations/2026_10_01_drop_email.php:14` · confidence 90 · migrations\n"
                "Old code reads it during the deploy.\n\n"
                "## Minor (1)\n\n- **[MIG-2]** `database/migrations/x.php:3` — no down() "
                "(confidence 81, migrations, also raised by completeness)\n")
        a, b = ef.parse_report(text)
        self.assertEqual((a["id"], a["pass"]), ("MIG-1", "migrations"))
        self.assertEqual((b["id"], b["pass"]), ("MIG-2", "migrations"))
        self.assertEqual(ef.validate_findings([a, b]), [])

    def test_heading_with_no_body_uses_the_title(self):
        text = "## Major (1)\n\n### [COR-3] Off by one\n`x.py:4` · confidence 90 · correctness\n**Fix:** use <=\n"
        (f,) = ef.parse_report(text)
        self.assertEqual(f["body"], "Off by one")
        self.assertEqual(ef.validate_findings([f]), [])

    def test_empty_report_parses_to_nothing(self):
        self.assertEqual(ef.parse_report(""), [])
        self.assertEqual(ef.parse_report("# Four-pass review\n\n**Verdict:** PASS\n"), [])


class Main(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.report = os.path.join(self.dir, "report.md")
        with open(self.report, "w", encoding="utf-8") as fh:
            fh.write(REPORT)

    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ef.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_prints_json_to_stdout_by_default(self):
        code, out, _ = self._run([self.report])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(len(data), 4)
        self.assertEqual(data[0]["id"], "COR-1")

    def test_writes_json_to_out_file(self):
        target = os.path.join(self.dir, "findings.json")
        code, out, err = self._run([self.report, "--out", target])
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertIn("4 finding(s)", err)
        with open(target, encoding="utf-8") as fh:
            self.assertEqual(len(json.load(fh)), 4)

    def test_contract_breaking_report_exits_1(self):
        # Two findings with the same id: parseable, but not a valid findings list.
        with open(self.report, "w", encoding="utf-8") as fh:
            fh.write("## Major (2)\n\n### [COR-1] A\n`x.py:1` · confidence 90 · correctness\nbody\n\n"
                     "### [COR-1] B\n`y.py:2` · confidence 90 · correctness\nbody\n")
        code, out, err = self._run([self.report])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("id repeats finding 0", err)
        self.assertIn("finding contract", err)

    def test_no_findings_exits_1_with_a_message(self):
        with open(self.report, "w", encoding="utf-8") as fh:
            fh.write("# Four-pass review: PR #1\n\n**Verdict:** PASS\n\n## Pass summaries\n")
        code, out, err = self._run([self.report])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("no findings parsed", err)

    def test_unreadable_report_exits_1(self):
        code, _, err = self._run([os.path.join(self.dir, "missing.md")])
        self.assertEqual(code, 1)
        self.assertIn("cannot read", err)


if __name__ == "__main__":
    unittest.main()
