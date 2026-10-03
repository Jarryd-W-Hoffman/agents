#!/usr/bin/env python3
"""Tests for skills/map/scripts/impact-scan.py and impact_contract.py.

Run: python3 tests/test_impact_scan.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "skills", "map", "scripts")


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


scan_mod = load("impact_scan", "impact-scan.py")
contract = load("impact_contract", "impact_contract.py")

SERVICE_BASE = """<?php

namespace App\\Services;

class InvoiceService
{
    public function total(Invoice $invoice): int
    {
        return $invoice->lines->sum('amount');
    }

    public function overdue(): array
    {
        return [];
    }
}
"""
SERVICE_HEAD = SERVICE_BASE.replace(
    "return $invoice->lines->sum('amount');",
    "return $invoice->lines->sum('amount') - $invoice->discount;")
CONTROLLER = """<?php

namespace App\\Http\\Controllers;

class InvoiceController extends Controller
{
    public function show(Invoice $invoice, InvoiceService $service): array
    {
        return ['total' => $service->total($invoice)];
    }
}
"""
ROUTES = """<?php

Route::get('/invoices/{invoice}', [InvoiceController::class, 'show']);
"""
JOB = """<?php

class SendInvoiceReminder implements ShouldQueue
{
    public function handle(InvoiceService $service): void
    {
        $sum = $service->total($this->invoice);
    }
}
"""
TEST = """<?php

it('totals lines', function () {
    expect(app(InvoiceService::class)->total($invoice))->toBe(10);
});
"""
TOKEN = """<?php

class TokenService
{
    public function total(): int { return 0; }
}
"""
DIFF = """diff --git a/app/Services/InvoiceService.php b/app/Services/InvoiceService.php
--- a/app/Services/InvoiceService.php
+++ b/app/Services/InvoiceService.php
@@ -9 +9 @@ class InvoiceService
-        return $invoice->lines->sum('amount');
+        return $invoice->lines->sum('amount') - $invoice->discount;
"""


def memory_search(files: dict[str, str]):
    def search(name: str, rev: str):
        out = []
        for path, text in files.items():
            for i, line in enumerate(text.splitlines(), start=1):
                if re.search(rf"(?<![\w$]){re.escape(name)}(?![\w$])", line):
                    out.append((path, i, line))
        return out
    return search


REPO_FILES = {
    "app/Services/InvoiceService.php": SERVICE_HEAD,
    "app/Http/Controllers/InvoiceController.php": CONTROLLER,
    "routes/web.php": ROUTES,
    "app/Jobs/SendInvoiceReminder.php": JOB,
    "tests/Feature/InvoiceTest.php": TEST,
    "app/Services/TokenService.php": TOKEN,
}


class Declarations(unittest.TestCase):
    def names(self, path, text):
        return [(d["kind"], scan_mod.symbol_name(d)) for d in scan_mod.declarations(path, text)]

    def test_php(self):
        self.assertEqual(self.names("a.php", SERVICE_BASE), [
            ("class", "InvoiceService"), ("method", "InvoiceService::total"),
            ("method", "InvoiceService::overdue")])

    def test_python(self):
        src = "class A:\n    def m(self):\n        pass\n\ndef f():\n    pass\n"
        self.assertEqual(self.names("a.py", src),
                         [("class", "A"), ("method", "A::m"), ("function", "f")])

    def test_javascript(self):
        src = ("export class Cart {\n  total(items) {\n    return 1;\n  }\n}\n"
               "export function render(x) {\n}\nconst sum = (a, b) => a + b;\n"
               "  if (x) {\n")
        self.assertEqual(self.names("a.ts", src), [
            ("class", "Cart"), ("method", "Cart::total"), ("function", "render"),
            ("function", "sum")])

    def test_go(self):
        src = "type Cart struct {\n}\nfunc (c *Cart) Total() int {\n}\nfunc Render() {\n}\n"
        self.assertEqual(self.names("a.go", src), [
            ("class", "Cart"), ("method", "Cart::Total"), ("function", "Render")])

    def test_unknown_language_has_none(self):
        self.assertEqual(scan_mod.declarations("a.txt", "class A {}"), [])


class Enclosing(unittest.TestCase):
    def test_line_in_a_method(self):
        decls = scan_mod.declarations("a.php", SERVICE_BASE)
        d = scan_mod.enclosing(decls, 9, SERVICE_BASE.splitlines(), "php")
        self.assertEqual(scan_mod.symbol_name(d), "InvoiceService::total")

    def test_line_before_any_declaration_is_file_level(self):
        decls = scan_mod.declarations("a.php", SERVICE_BASE)
        self.assertIsNone(scan_mod.enclosing(decls, 3, SERVICE_BASE.splitlines(), "php"))

    def test_python_dedent_leaves_the_function(self):
        src = "class A:\n    def m(self):\n        pass\n    X = 1\n"
        decls = scan_mod.declarations("a.py", src)
        d = scan_mod.enclosing(decls, 4, src.splitlines(), "py")
        self.assertEqual(scan_mod.symbol_name(d), "A")


class Category(unittest.TestCase):
    def test_categories(self):
        cases = {"app/Services/X.php": "code", "tests/Unit/XTest.php": "test",
                 "README.md": "doc", "composer.lock": "other", "config/app.php": "code",
                 "phpstan.neon": "config", ".env.example": "config", "x_test.go": "test",
                 "resources/views/a.blade.php": "code", "logo.png": "other",
                 "scripts/check.sh": "code"}
        for path, want in cases.items():
            self.assertEqual(scan_mod.category(path), want, path)


class ChangedLines(unittest.TestCase):
    def test_parses_hunks(self):
        got = scan_mod.changed_lines(DIFF)["app/Services/InvoiceService.php"]
        self.assertEqual((got["head"], got["base"]), ({9}, {9}))

    def test_deleted_file_is_keyed_by_its_base_path(self):
        diff = "--- a/old.php\n+++ /dev/null\n@@ -1,3 +0,0 @@\n-a\n-b\n-c\n"
        got = scan_mod.changed_lines(diff)
        self.assertEqual(got["old.php"]["base"], {1, 2, 3})

    def test_rename_keeps_the_base_path(self):
        diff = "--- a/old.php\n+++ b/new.php\n@@ -2 +2 @@\n-a\n+b\n"
        self.assertEqual(scan_mod.changed_lines(diff)["new.php"]["base_path"], "old.php")

    def test_pure_insertion_has_no_base_lines(self):
        diff = "--- a/x.php\n+++ b/x.php\n@@ -4,0 +5,2 @@\n+a\n+b\n"
        got = scan_mod.changed_lines(diff)["x.php"]
        self.assertEqual((got["head"], got["base"]), ({5, 6}, set()))


class Scan(unittest.TestCase):
    def setUp(self):
        self.result = scan_mod.scan({"app/Services/InvoiceService.php": SERVICE_BASE},
                                    REPO_FILES, DIFF, memory_search(REPO_FILES))
        (self.sym,) = self.result["symbols"]

    def test_finds_the_changed_method(self):
        s = self.sym
        self.assertEqual((s["symbol"], s["kind"], s["change"], s["line"]),
                         ("InvoiceService::total", "method", "modified", 7))
        self.assertFalse(s["signature_changed"])
        self.assertTrue(self.result["analyse"])

    def test_references_are_tagged(self):
        by_path = {r["path"]: r for r in self.sym["references"]}
        self.assertIn("app/Http/Controllers/InvoiceController.php", by_path)
        self.assertEqual(by_path["app/Jobs/SendInvoiceReminder.php"]["entry_hint"], "queue")
        self.assertTrue(by_path["tests/Feature/InvoiceTest.php"]["in_test"])

    def test_definitions_are_not_references(self):
        # TokenService::total is a different method with the same name. Its
        # declaration must not count; telling call sites apart is the agent's job.
        self.assertNotIn("app/Services/TokenService.php", {r["path"] for r in self.sym["references"]})
        self.assertNotIn(("app/Services/InvoiceService.php", 7),
                         {(r["path"], r["line"]) for r in self.sym["references"]})

    def test_signature_change_is_detected(self):
        head = SERVICE_HEAD.replace("total(Invoice $invoice): int", "total(Invoice $invoice, bool $tax = false): int")
        diff = DIFF.replace("@@ -9 +9 @@", "@@ -7 +7 @@\n-    public function total(Invoice $invoice): int\n"
                            "+    public function total(Invoice $invoice, bool $tax = false): int\n@@ -9 +9 @@")
        files = dict(REPO_FILES, **{"app/Services/InvoiceService.php": head})
        r = scan_mod.scan({"app/Services/InvoiceService.php": SERVICE_BASE}, files, diff, memory_search(files))
        self.assertTrue(r["symbols"][0]["signature_changed"])

    def test_removed_method_reports_dangling_head_references(self):
        head = SERVICE_BASE.replace("""    public function overdue(): array
    {
        return [];
    }
""", "")
        diff = ("--- a/app/Services/InvoiceService.php\n+++ b/app/Services/InvoiceService.php\n"
                "@@ -12,4 +11,0 @@\n-a\n-b\n-c\n-d\n")
        caller = "<?php\n$x = $service->overdue();\n"
        files = {"app/Services/InvoiceService.php": head, "app/Console/Commands/Remind.php": caller}
        r = scan_mod.scan({"app/Services/InvoiceService.php": SERVICE_BASE}, files, diff, memory_search(files))
        (s,) = r["symbols"]
        self.assertEqual((s["symbol"], s["change"]), ("InvoiceService::overdue", "removed"))
        heads = [x for x in s["references"] if x["rev"] == "head"]
        self.assertEqual([(x["path"], x["entry_hint"]) for x in heads],
                         [("app/Console/Commands/Remind.php", "console")])

    def test_changed_controller_is_its_own_entry_point(self):
        head = CONTROLLER.replace("['total' =>", "['sum' =>")
        diff = ("--- a/app/Http/Controllers/InvoiceController.php\n"
                "+++ b/app/Http/Controllers/InvoiceController.php\n@@ -9 +9 @@\n-a\n+b\n")
        files = dict(REPO_FILES, **{"app/Http/Controllers/InvoiceController.php": head})
        r = scan_mod.scan({"app/Http/Controllers/InvoiceController.php": CONTROLLER}, files, diff,
                          memory_search(files))
        (s,) = r["symbols"]
        self.assertEqual((s["symbol"], s["entry"]), ("InvoiceController::show", "http"))
        # The route names the method as a string; the filter keeps it.
        self.assertIn("routes/web.php", {x["path"] for x in s["references"]})

    def test_constructor_change_searches_the_class(self):
        base = "<?php\nclass OrderPlaced\n{\n    public function __construct(public int $total)\n    {\n    }\n}\n"
        head = base.replace("int $total", "int $totalCents")
        diff = "--- a/app/Events/OrderPlaced.php\n+++ b/app/Events/OrderPlaced.php\n@@ -4 +4 @@\n-a\n+b\n"
        files = {"app/Events/OrderPlaced.php": head,
                 "app/Providers/EventServiceProvider.php": "<?php\nOrderPlaced::class => [SendConfirmation::class],\n",
                 "app/Models/Other.php": "<?php\nclass Other { public function __construct() {} }\n"}
        r = scan_mod.scan({"app/Events/OrderPlaced.php": base}, files, diff, memory_search(files))
        (s,) = r["symbols"]
        self.assertEqual(s["symbol"], "OrderPlaced::__construct")
        self.assertTrue(s["signature_changed"])
        paths = {x["path"] for x in s["references"]}
        self.assertEqual(paths, {"app/Providers/EventServiceProvider.php"})
        self.assertEqual(s["references"][0]["entry_hint"], "event")

    def test_references_are_capped(self):
        many = {f"app/C{i}.php": "<?php $s->total($x);\n" for i in range(scan_mod.REF_CAP + 5)}
        files = dict(REPO_FILES, **many)
        r = scan_mod.scan({"app/Services/InvoiceService.php": SERVICE_BASE}, files, DIFF, memory_search(files))
        s = r["symbols"][0]
        self.assertTrue(s["truncated"])
        self.assertEqual(len(s["references"]), scan_mod.REF_CAP)
        self.assertGreater(s["total_references"], scan_mod.REF_CAP)


class NothingToAnalyse(unittest.TestCase):
    def run_scan(self, paths):
        diff = "".join(f"--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-a\n+b\n" for p in paths)
        files = {p: "b\n" for p in paths}
        return scan_mod.scan({p: "a\n" for p in paths}, files, diff, memory_search(files))

    def test_docs_tests_and_lockfiles_alone(self):
        r = self.run_scan(["README.md", "tests/Unit/XTest.php", "composer.lock"])
        self.assertFalse(r["analyse"])
        self.assertEqual(r["symbols"], [])
        self.assertIn("only", r["reason"])

    def test_config_counts(self):
        self.assertTrue(self.run_scan(["phpstan.neon"])["analyse"])

    def test_code_counts(self):
        self.assertTrue(self.run_scan(["app/X.php"])["analyse"])


class DraftImpact(unittest.TestCase):
    def setUp(self):
        result = scan_mod.scan({"app/Services/InvoiceService.php": SERVICE_BASE},
                               REPO_FILES, DIFF, memory_search(REPO_FILES))
        self.impact = scan_mod.to_impact(result, "working tree", "HEAD", "working tree")

    def test_satisfies_the_contract(self):
        self.assertEqual(contract.validate(self.impact), [])

    def test_is_marked_quick_and_unverified(self):
        self.assertEqual(self.impact["mode"], "quick")
        self.assertTrue(all(not c["verified"] for c in self.impact["callers"]))
        self.assertTrue(self.impact["limits"])

    def test_tests_and_entry_points(self):
        self.assertEqual(self.impact["tests"]["covering"],
                         [{"path": "tests/Feature/InvoiceTest.php", "reaches": ["InvoiceService::total"]}])
        self.assertEqual(self.impact["tests"]["uncovered"], [])
        self.assertIn("queue", {e["kind"] for e in self.impact["entry_points"]})


class Contract(unittest.TestCase):
    def good(self):
        result = scan_mod.scan({"app/Services/InvoiceService.php": SERVICE_BASE},
                               REPO_FILES, DIFF, memory_search(REPO_FILES))
        return scan_mod.to_impact(result, "t", "b", "h")

    def assert_error(self, impact, fragment):
        errors = contract.validate(impact)
        self.assertTrue(any(fragment in e for e in errors), f"{fragment!r} not in {errors}")

    def test_unknown_field(self):
        impact = self.good()
        impact["severity"] = "high"
        self.assert_error(impact, "unknown field 'severity'")

    def test_risk_needs_evidence(self):
        impact = self.good()
        impact["risks"] = [{"area": "billing", "why": "totals change", "evidence": []}]
        self.assert_error(impact, "must cite at least one")

    def test_evidence_shape(self):
        impact = self.good()
        impact["risks"] = [{"area": "a", "why": "w", "evidence": ["somewhere"]}]
        self.assert_error(impact, "does not match")

    def test_ref_paths_are_checked(self):
        impact = self.good()
        impact["changed"][0]["path"] = "/abs/path.php"
        self.assert_error(impact, "does not match")

    def test_mode_and_version(self):
        impact = self.good()
        impact["mode"] = "deep"
        impact["version"] = 2
        self.assert_error(impact, "'deep' is not one of")
        self.assert_error(impact, "2 is not one of")

    def test_bool_fields(self):
        impact = self.good()
        impact["callers"][0]["verified"] = "yes"
        self.assert_error(impact, "expected boolean")

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "impact.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.good(), fh)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(contract.main([path]), 0)
                self.assertEqual(contract.main([]), 2)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class AgainstGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def g(self, *a):
        subprocess.run(["git", "-C", self.tmp, *a], check=True, capture_output=True)

    def write(self, rel, text):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = scan_mod.main(argv)
        return code, out.getvalue(), err.getvalue()

    def commit_base(self):
        self.g("init", "-q")
        self.g("config", "user.email", "t@example.com")
        self.g("config", "user.name", "t")
        for path, text in REPO_FILES.items():
            self.write(path, SERVICE_BASE if path == "app/Services/InvoiceService.php" else text)
        self.g("add", ".")
        self.g("commit", "-q", "-m", "base")

    def test_working_tree_with_an_untracked_caller(self):
        self.commit_base()
        self.write("app/Services/InvoiceService.php", SERVICE_HEAD)
        self.write("app/Console/Commands/Totals.php", "<?php\n$s->total($i);\n")
        os.chdir(self.tmp)
        code, out, err = self.run_main(["--base", "HEAD"])
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        total = next(s for s in data["symbols"] if s["symbol"] == "InvoiceService::total")
        paths = {r["path"] for r in total["references"]}
        self.assertIn("app/Jobs/SendInvoiceReminder.php", paths)
        self.assertIn("app/Console/Commands/Totals.php", paths, "untracked files must be searched")

    def test_commit_range_and_draft_impact(self):
        self.commit_base()
        self.write("app/Services/InvoiceService.php", SERVICE_HEAD)
        self.g("commit", "-q", "-am", "head")
        os.chdir(self.tmp)
        code, out, err = self.run_main(["--base", "HEAD~1", "--head", "HEAD", "--impact-json"])
        self.assertEqual(code, 0, err)
        impact = json.loads(out)
        self.assertEqual(contract.validate(impact), [])
        self.assertEqual([c["symbol"] for c in impact["changed"]], ["InvoiceService::total"])

    def test_not_a_repository(self):
        os.chdir(self.tmp)
        code, out, err = self.run_main(["--base", "HEAD"])
        self.assertEqual(code, 1)
        self.assertIn("impact-scan:", err)


if __name__ == "__main__":
    unittest.main(verbosity=1)
