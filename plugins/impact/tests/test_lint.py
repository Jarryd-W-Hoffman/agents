#!/usr/bin/env python3
"""Static checks over this repo's own Python, using the standard library only.

Not a general-purpose linter. It covers the specific mistakes this codebase is
prone to, mostly refactoring residue such as dead imports and unused names. It
is a copy of the fourpass plugin's lint test: each plugin is
self-contained and may not import from a sibling.

The repo is standard-library-only by policy, and the hooks run under whatever
`python3` the user has. Adding ruff or flake8 would mean a dependency and an
install step in CI for a codebase this size; these are the rules that actually
earn their keep here.

Run: python3 tests/test_lint.py
"""

from __future__ import annotations

import ast
import os
import py_compile
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Directories whose .py files are checked. Eval fixtures are excluded on
# purpose: they are deliberately small Laravel apps for the analyst to map.
SOURCE_DIRS = ("hooks", "skills", "tests", "evals")
EXCLUDE = (os.path.join("evals", "fixtures"), os.path.join("evals", "results"))


def python_files() -> list[str]:
    out = []
    for d in SOURCE_DIRS:
        for root, _, names in os.walk(os.path.join(REPO, d)):
            rel = os.path.relpath(root, REPO)
            if any(rel == e or rel.startswith(e + os.sep) for e in EXCLUDE):
                continue
            out.extend(os.path.join(root, n) for n in names if n.endswith(".py"))
    return sorted(out)


def parse(path: str) -> ast.Module:
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), path)


def imported_names(tree: ast.Module) -> dict[str, int]:
    """Imported name -> line. Star imports contribute nothing checkable."""
    out: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out[(alias.asname or alias.name).split(".")[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    out[alias.asname or alias.name] = node.lineno
    return out


def referenced_names(tree: ast.Module) -> set[str]:
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
            if isinstance(node.value, ast.Name):
                used.add(node.value.id)
    return used


class Lint(unittest.TestCase):
    def setUp(self):
        self.files = python_files()
        self.assertTrue(self.files, "found no Python to check")

    def rel(self, path: str) -> str:
        return os.path.relpath(path, REPO)

    def test_every_file_compiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in self.files:
                with self.subTest(file=self.rel(path)):
                    py_compile.compile(
                        path, cfile=os.path.join(tmp, "out.pyc"), doraise=True)

    def test_no_unused_imports(self):
        # The exact residue the guard split left behind.
        for path in self.files:
            tree = parse(path)
            used = referenced_names(tree)
            for name, line in sorted(imported_names(tree).items(), key=lambda kv: kv[1]):
                if name == "annotations":  # `from __future__ import annotations`
                    continue
                with self.subTest(file=self.rel(path), name=name):
                    self.assertIn(name, used,
                                  f"{self.rel(path)}:{line}: `{name}` is imported "
                                  "but never used")

    def test_no_mutable_default_arguments(self):
        for path in self.files:
            for node in ast.walk(parse(path)):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                defaults = node.args.defaults + [d for d in node.args.kw_defaults if d]
                for default in defaults:
                    with self.subTest(file=self.rel(path), func=node.name):
                        self.assertNotIsInstance(
                            default, (ast.List, ast.Dict, ast.Set),
                            f"{self.rel(path)}:{node.lineno}: {node.name}() has a "
                            "mutable default argument")

    def test_no_bare_except(self):
        # The guard and the poster both fail closed deliberately; they should
        # say which exceptions they mean, so a real bug is not swallowed too.
        for path in self.files:
            for node in ast.walk(parse(path)):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    self.fail(f"{self.rel(path)}:{node.lineno}: bare `except:` "
                              "-- name the exceptions being handled")

    def test_no_tabs_and_no_trailing_whitespace(self):
        for path in self.files:
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    stripped = line.rstrip("\n")
                    with self.subTest(file=self.rel(path), line=n):
                        self.assertNotIn("\t", stripped, "tab in source")
                        self.assertEqual(stripped, stripped.rstrip(),
                                         "trailing whitespace")

    def test_files_end_with_exactly_one_newline(self):
        for path in self.files:
            with open(path, "rb") as fh:
                data = fh.read()
            with self.subTest(file=self.rel(path)):
                self.assertTrue(data.endswith(b"\n"), "no trailing newline")
                self.assertFalse(data.endswith(b"\n\n"), "blank line at end of file")


class Executables(unittest.TestCase):
    """Anything meant to be run directly has to be runnable."""

    def test_scripts_with_a_shebang_are_executable_or_imported(self):
        # The guard is invoked as `python3 <path>`, so it need not be +x; but a
        # file claiming a shebang should at least have a correct one.
        for path in python_files():
            with open(path, encoding="utf-8") as fh:
                first = fh.readline()
            if first.startswith("#!"):
                with self.subTest(file=os.path.relpath(path, REPO)):
                    self.assertIn("python3", first,
                                  f"shebang does not name python3: {first.strip()}")


if __name__ == "__main__":
    unittest.main(verbosity=1)
