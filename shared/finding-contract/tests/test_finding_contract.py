#!/usr/bin/env python3
"""Tests for finding_contract.py. Run: python3 shared/finding-contract/tests/test_finding_contract.py"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("finding_contract",
                                              os.path.join(HERE, "finding_contract.py"))
fc = importlib.util.module_from_spec(spec)
sys.modules["finding_contract"] = fc
spec.loader.exec_module(fc)  # type: ignore[union-attr]


def finding(**kw):
    base = {"id": "COR-1", "title": "Null customer", "severity": "critical",
            "confidence": 92, "pass": "correctness", "path": "billing/exporter.py",
            "line": 7, "body": "customer is optional on API-created invoices."}
    base.update(kw)
    return {k: v for k, v in base.items() if v is not None}


def without(key):
    f = finding()
    del f[key]
    return f


class Valid(unittest.TestCase):
    def test_minimal_finding(self):
        self.assertEqual(fc.validate([finding()]), [])

    def test_every_optional_field(self):
        f = finding(end_line=9, side="RIGHT", fix="Guard it.", suggestion="x = 1")
        self.assertEqual(fc.validate([f]), [])

    def test_empty_list(self):
        self.assertEqual(fc.validate([]), [])

    def test_passes_are_open_ended(self):
        for p in ("migrations", "adhoc", "completeness"):
            self.assertEqual(fc.validate([finding(**{"pass": p})]), [], p)

    def test_prefixes_are_open_ended(self):
        for fid in ("MIG-1", "ADHOC-1", "CPL-12"):
            self.assertEqual(fc.validate([finding(id=fid)]), [], fid)

    def test_single_line_range(self):
        self.assertEqual(fc.validate([finding(line=4, end_line=4)]), [])


class Invalid(unittest.TestCase):
    def assert_error(self, findings, fragment):
        errors = fc.validate(findings)
        self.assertTrue(any(fragment in e for e in errors),
                        f"no error containing {fragment!r} in {errors}")

    def test_not_a_list(self):
        self.assert_error({"findings": []}, "expected array")

    def test_entry_not_an_object(self):
        self.assert_error(["COR-1"], "expected object")

    def test_each_required_field(self):
        for key in fc.load_schema()["items"]["required"]:
            self.assert_error([without(key)], f"missing required field '{key}'")

    def test_unknown_field_is_named(self):
        # A typo such as "file" for "path" must not pass as an extra.
        self.assert_error([finding(file="x.py")], "unknown field 'file'")

    def test_severity_outside_the_scale(self):
        self.assert_error([finding(severity="high")], "is not one of")

    def test_confidence_bounds_and_type(self):
        self.assert_error([finding(confidence=101)], "above 100")
        self.assert_error([finding(confidence=-1)], "below 0")
        self.assert_error([finding(confidence=92.5)], "expected integer")
        self.assert_error([finding(confidence="92")], "expected integer")

    def test_bool_is_not_an_integer(self):
        self.assert_error([finding(line=True)], "expected integer")

    def test_line_starts_at_one(self):
        self.assert_error([finding(line=0)], "below 1")

    def test_id_shape(self):
        for bad in ("cor-1", "COR1", "COR-", "-1", "COR-1a"):
            self.assert_error([finding(id=bad)], "does not match")

    def test_pass_shape(self):
        for bad in ("Correctness", "", "migration safety"):
            self.assertTrue(fc.validate([finding(**{"pass": bad})]), bad)

    def test_path_must_be_repo_relative(self):
        for bad in ("/etc/passwd", "../outside.py", "a/../../b.py", "\\\\host\\x", "C:/x.py"):
            self.assert_error([finding(path=bad)], "does not match")

    def test_dotdot_inside_a_name_is_fine(self):
        self.assertEqual(fc.validate([finding(path="docs/a..b.md")]), [])

    def test_empty_strings(self):
        self.assert_error([finding(title="")], "must not be empty")
        self.assert_error([finding(body="")], "must not be empty")

    def test_side_enum(self):
        self.assert_error([finding(side="left")], "is not one of")

    def test_end_line_before_line(self):
        self.assert_error([finding(line=9, end_line=7)], "end_line 7 is before line 9")

    def test_duplicate_ids(self):
        self.assert_error([finding(), finding(line=8)], "id repeats finding 0")

    def test_errors_name_the_finding_by_id(self):
        errors = fc.validate([finding(), finding(id="CMP-2", line=0)])
        self.assertIn("finding 1 (CMP-2).line: 0 is below 1", errors)

    def test_reports_every_error_not_just_the_first(self):
        errors = fc.validate([finding(severity="high", confidence=200, line=0)])
        self.assertEqual(len(errors), 3, errors)


class Schema(unittest.TestCase):
    """The validator handles exactly the keywords the schema uses."""

    HANDLED = {"$schema", "$id", "title", "description", "type", "items", "required",
               "properties", "additionalProperties", "enum", "pattern", "minLength",
               "minimum", "maximum"}

    def walk(self, node):
        if isinstance(node, dict):
            yield from node.keys()
            for k, v in node.items():
                if k == "properties":
                    for sub in v.values():
                        yield from self.walk(sub)
                elif isinstance(v, dict):
                    yield from self.walk(v)

    def test_no_unhandled_keyword(self):
        # A keyword added to the schema that the validator ignores would be a
        # rule that is documented and never enforced.
        unhandled = set(self.walk(fc.load_schema())) - self.HANDLED
        self.assertEqual(unhandled, set())

    def test_every_type_used_is_known(self):
        types = {fc.load_schema()["type"], fc.load_schema()["items"]["type"]}
        types |= {p["type"] for p in fc.load_schema()["items"]["properties"].values()}
        self.assertLessEqual(types, set(fc._TYPES))


class Cli(unittest.TestCase):
    def run_cli(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "findings.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(payload if isinstance(payload, str) else json.dumps(payload))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = fc.main([path])
        return code, err.getvalue()

    def test_valid_file_exits_0(self):
        code, err = self.run_cli([finding()])
        self.assertEqual(code, 0)
        self.assertIn("1 finding(s) valid", err)

    def test_invalid_file_exits_1_with_each_error(self):
        code, err = self.run_cli([finding(severity="high"), without("path")])
        self.assertEqual(code, 1)
        self.assertIn("finding 0 (COR-1).severity", err)
        self.assertIn("missing required field 'path'", err)

    def test_malformed_json_exits_1(self):
        code, err = self.run_cli("[{")
        self.assertEqual(code, 1)
        self.assertIn("cannot read", err)

    def test_usage(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(fc.main([]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
