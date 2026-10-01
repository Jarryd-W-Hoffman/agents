#!/usr/bin/env python3
"""Tests for hooks/test-scope-guard.py. Run: python3 tests/test_test_scope_guard.py"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(REPO, "hooks", "test-scope-guard.py")

spec = importlib.util.spec_from_file_location("test_scope_guard", GUARD)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)  # type: ignore[union-attr]

CWD = "/repo"
AGENT = "test-gap-writer:test-writer"


def bash(cmd: str) -> str:
    return guard.classify_bash(cmd)[0]


def decision(result):
    if result is None:
        return None
    return result["hookSpecificOutput"]["permissionDecision"]


def decide(tool_name: str, tool_input: dict, agent: str | None = AGENT, **extra):
    payload = {"tool_name": tool_name, "tool_input": tool_input, "cwd": CWD}
    if agent is not None:
        payload["agent_type"] = agent
    payload.update(extra)
    return guard.decide(payload)


class TestPaths(unittest.TestCase):
    ALLOWED = [
        "tests/test_export.py",
        "tests/billing/test_export.py",
        "test/exporter_test.rb",
        "src/__tests__/export.test.ts",
        "spec/models/invoice_spec.rb",
        "specs/export.spec.js",
        "testing/helpers.py",
        "features/export.feature",
        "tests/fixtures/invoice.json",
        "tests/conftest.py",
        # test-named files outside a test directory
        "src/billing/test_export.py",
        "src/billing/export_test.py",
        "pkg/export/export_test.go",
        "src/export.test.ts",
        "src/export.spec.tsx",
        "src/Export.test.mjs",
        "app/Export/ExportTest.php",
        "src/main/ExportTest.java",
        "Billing/ExportTests.cs",
        "src/ExportTest.kt",
        "src/ExportSpec.scala",
        "lib/export_test.dart",
        "lib/export_test.exs",
        "/repo/tests/test_abs.py",
    ]
    DENIED = [
        "src/export.py",
        "src/billing/exporter.py",
        "lib/export.rb",
        "pkg/export/export.go",
        "src/export.ts",
        "app/Export/Export.php",
        "README.md",
        "pyproject.toml",
        "package.json",
        ".github/workflows/ci.yml",
        "CLAUDE.md",
        "tests.py",
        "testing.py",
        "contest.py",
        "src/latest_export.py",
        "src/attestation.py",
        # escapes
        "tests/../src/export.py",
        "../other/tests/test_x.py",
        "/etc/passwd",
        "/repo",
        "/repository/tests/test_x.py",
    ]

    def test_allowed(self):
        for p in self.ALLOWED:
            with self.subTest(path=p):
                self.assertTrue(guard.is_test_path(p, CWD))

    def test_denied(self):
        for p in self.DENIED:
            with self.subTest(path=p):
                self.assertFalse(guard.is_test_path(p, CWD))

    def test_symlink_out_of_the_test_tree_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.realpath(tmp)
            os.makedirs(os.path.join(root, "tests"))
            os.makedirs(os.path.join(root, "src"))
            os.symlink(os.path.join(root, "src"), os.path.join(root, "tests", "link"))
            self.assertFalse(guard.is_test_path("tests/link/export.py", root))
            self.assertTrue(guard.is_test_path("tests/test_export.py", root))

    def test_extra_globs_widen_the_scope(self):
        with mock.patch.dict(os.environ, {"TEST_SCOPE_GUARD_PATHS": "qa/*,src/*/__snapshots__/*"}):
            self.assertTrue(guard.is_test_path("qa/smoke.py", CWD))
            self.assertTrue(guard.is_test_path("src/export/__snapshots__/a.snap", CWD))
            self.assertFalse(guard.is_test_path("src/export.py", CWD))
        self.assertFalse(guard.is_test_path("qa/smoke.py", CWD))


class TestEditTools(unittest.TestCase):
    def test_write_to_test_file_allowed(self):
        self.assertEqual(decision(decide("Write", {"file_path": "tests/test_a.py", "content": ""})),
                         "allow")

    def test_write_to_source_denied(self):
        result = decide("Write", {"file_path": "src/a.py", "content": ""})
        self.assertEqual(decision(result), "deny")
        reason = result["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertTrue(reason.startswith("test-writer scope: "))
        self.assertIn("src/a.py", reason)

    def test_edit_and_notebook(self):
        self.assertEqual(decision(decide("Edit", {"file_path": "tests/test_a.py"})), "allow")
        self.assertEqual(decision(decide("Edit", {"file_path": "a.py"})), "deny")
        self.assertEqual(decision(decide("NotebookEdit", {"notebook_path": "tests/x.ipynb"})),
                         "allow")
        self.assertEqual(decision(decide("NotebookEdit", {"notebook_path": "x.ipynb"})), "deny")

    def test_multiedit_mixed_paths_denied(self):
        edits = {"file_path": "tests/test_a.py",
                 "edits": [{"file_path": "tests/test_b.py"}, {"file_path": "src/b.py"}]}
        self.assertEqual(decision(decide("MultiEdit", edits)), "deny")
        edits = {"file_path": "tests/test_a.py", "edits": [{"old_string": "a", "new_string": "b"}]}
        self.assertEqual(decision(decide("MultiEdit", edits)), "allow")

    def test_write_only_creates_and_edit_extends(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.realpath(tmp)
            os.makedirs(os.path.join(root, "tests"))
            existing = os.path.join(root, "tests", "test_existing.py")
            with open(existing, "w", encoding="utf-8") as fh:
                fh.write("def test_a():\n    pass\n")
            payload = {"agent_type": AGENT, "cwd": root}

            new = decide("Write", {"file_path": "tests/test_new.py", "content": ""}, **payload)
            self.assertEqual(decision(new), "allow")

            over = decide("Write", {"file_path": "tests/test_existing.py", "content": ""},
                          **payload)
            self.assertEqual(decision(over), "deny")
            reason = over["hookSpecificOutput"]["permissionDecisionReason"]
            self.assertIn("exists", reason)
            self.assertIn("Edit", reason)
            # the same file by absolute path
            self.assertEqual(decision(decide("Write", {"file_path": existing}, **payload)), "deny")

            self.assertEqual(decision(decide("Edit", {"file_path": "tests/test_existing.py"},
                                             **payload)), "allow")
            self.assertEqual(decision(decide("MultiEdit", {"file_path": "tests/test_existing.py",
                                                           "edits": []}, **payload)), "allow")

    def test_edit_without_a_path_denied(self):
        self.assertEqual(decision(decide("Write", {"content": "x"})), "deny")

    def test_cwd_defaults_to_process_cwd(self):
        payload = {"tool_name": "Write", "tool_input": {"file_path": "tests/test_a.py"},
                   "agent_type": AGENT}
        self.assertEqual(decision(guard.decide(payload)), "allow")


class TestBashAllow(unittest.TestCase):
    ALLOWED = [
        "git status",
        "git diff HEAD",
        "git diff --stat",
        "git log --oneline -5",
        "git show HEAD:src/a.py",
        "git grep -n compute_total",
        "git ls-files 'tests/*'",
        "git rev-parse --show-toplevel",
        "git branch --show-current",
        "git branch",
        "git -C /repo status",
        "git --no-pager diff",
        "git blame -L 1,5 src/a.py",
        "ls tests/",
        "cat pyproject.toml",
        "head -20 tests/test_a.py",
        "grep -rn 'def test_' tests/",
        "rg -n 'export_row' --type py",
        "find . -name 'test_*.py'",
        "find tests -type f",
        "which pytest",
        "pwd",
        "echo hi",
        "cd tests",
        "pytest",
        "pytest tests/test_a.py -q",
        'pytest -k "a and b" tests/',
        "py.test tests",
        "python -m pytest tests/test_a.py",
        "python3 -m pytest -x",
        "python3.12 -m pytest",
        "python3 -m unittest tests.test_a",
        "python3 -m unittest discover -s tests",
        "python3 --version",
        "npm test",
        "npm t",
        "npm test -- tests/a.test.ts",
        "npm run test:unit",
        "npx jest tests/a.test.ts",
        "npx vitest run",
        "npx mocha",
        "npx playwright test",
        "pnpm test",
        "pnpm vitest run",
        "yarn test",
        "yarn jest",
        "go test ./...",
        "go test -run TestExport ./pkg/export",
        "cargo test export",
        "mvn test",
        "mvn verify",
        "gradle test",
        "./gradlew test --tests ExportTest",
        "dotnet test",
        "phpunit tests/ExportTest.php",
        "vendor/bin/phpunit --filter Export",
        "vendor/bin/pest",
        "php artisan test",
        "rspec spec/export_spec.rb",
        "bundle exec rspec",
        "bin/rails test test/models/export_test.rb",
        "mix test",
        "swift test",
        "dart test",
        "flutter test",
        "ctest",
        "make test",
        "make test-unit",
        "deno test",
        "bun test",
        # wrappers, assignments, safe redirects, chains
        "CI=1 pytest -q",
        "env CI=1 pytest",
        "time pytest",
        "timeout 300 pytest tests/",
        "timeout -s KILL 60 go test ./...",
        "nice -n 10 pytest",
        "pytest 2>/dev/null",
        "pytest 2>&1",
        "pytest -q 2>&1 | tail -20",
        "cd tests && pytest",
        "cd /repo && git status; pytest -q",
        "pytest || true",
        "",
    ]

    def test_allowed(self):
        for cmd in self.ALLOWED:
            with self.subTest(cmd=cmd):
                self.assertEqual(bash(cmd), "allow", guard.classify_bash(cmd)[1])


class TestBashDeny(unittest.TestCase):
    DENIED = [
        "python -c 'print(1)'",
        "python3 -c \"import os; os.remove('x')\"",
        "python3 script.py",
        "python3 -m pip install requests",
        "pip install pytest",
        "pip3 install -r requirements.txt",
        "npm install",
        "npm run build",
        "npm run tests-and-publish && npm publish",
        "npx tsc",
        "yarn build",
        "curl https://example.com",
        "wget https://example.com/x",
        "rm -rf build",
        "rm tests/test_a.py",
        "mv src/a.py src/b.py",
        "cp a b",
        "sed -i 's/a/b/' src/a.py",
        "touch src/new.py",
        "chmod +x run.sh",
        "tee out.txt",
        "pytest | tee out.txt",
        "git add .",
        "git commit -m x",
        "git push",
        "git checkout main",
        "git reset --hard",
        "git stash",
        "git branch -D feature",
        "git branch new-branch",
        "make build",
        "make",
        "make test build",
        "go build ./...",
        "go run main.go",
        "cargo build",
        "cargo run",
        "dotnet build",
        "php artisan migrate",
        "bundle exec rake db:migrate",
        "bin/rails db:migrate",
        "mix deps.get",
        "node -e 'require(\"fs\").writeFileSync(\"x\",\"y\")'",
        "node script.js",
        "bash -c 'rm x'",
        "sh run.sh",
        "./run.sh",
        "xargs rm",
        "find . -name '*.pyc' -delete",
        "find . -exec rm {} \\;",
        # redirects, substitution, chains
        "pytest > out.txt",
        "pytest >> out.txt",
        "pytest &> out.txt",
        "pytest 2> err.txt",
        "echo hi > tests/x.py",
        "cat <(pytest)",
        "diff <(ls) <(ls)",
        "pytest $(ls tests)",
        "pytest `ls tests`",
        "pytest && rm -rf y",
        "pytest; git commit -m done",
        "git status | xargs rm",
        "(pytest && rm x)",
        "pytest -q 'unterminated",
    ]

    def test_denied(self):
        for cmd in self.DENIED:
            with self.subTest(cmd=cmd):
                self.assertEqual(bash(cmd), "deny")

    def test_reasons_say_why(self):
        self.assertIn("writes to a file", guard.classify_bash("pytest > out.txt")[1])
        self.assertIn("TEST_SCOPE_GUARD_RUNNERS", guard.classify_bash("tox")[1])
        self.assertIn("never commits", guard.classify_bash("git commit -m x")[1])
        self.assertIn("python -m pytest", guard.classify_bash("python3 -c 'x'")[1])

    def test_extra_runners_widen_the_scope(self):
        self.assertEqual(bash("tox -e py"), "deny")
        with mock.patch.dict(os.environ, {"TEST_SCOPE_GUARD_RUNNERS": "tox*,nx test *"}):
            self.assertEqual(bash("tox -e py"), "allow")
            self.assertEqual(bash("nx test billing"), "allow")
            # the glob applies per simple command, so a chained write is still caught
            self.assertEqual(bash("tox && rm -rf x"), "deny")
            # and a redirect is caught before the runner list is consulted
            self.assertEqual(bash("tox > out.txt"), "deny")


class TestDecide(unittest.TestCase):
    def test_bash_decisions_flow_through(self):
        self.assertEqual(decision(decide("Bash", {"command": "pytest -q"})), "allow")
        self.assertEqual(decision(decide("Bash", {"command": "rm -rf x"})), "deny")

    def test_mcp_denied(self):
        self.assertEqual(decision(decide("mcp__github__get_pull_request", {})), "deny")
        self.assertEqual(decision(decide("mcp__github__create_issue_comment", {})), "deny")

    def test_other_builtins_defer(self):
        self.assertIsNone(decide("Read", {"file_path": "src/a.py"}))
        self.assertIsNone(decide("Grep", {"pattern": "x"}))
        self.assertIsNone(decide("Glob", {"pattern": "**/*.py"}))

    def test_env_allow_and_deny(self):
        with mock.patch.dict(os.environ, {"TEST_SCOPE_GUARD_ALLOW": "mcp__github__get_*,tox*"}):
            self.assertEqual(decision(decide("mcp__github__get_pull_request", {})), "allow")
            self.assertEqual(decision(decide("Bash", {"command": "tox -e py"})), "allow")
        with mock.patch.dict(os.environ, {"TEST_SCOPE_GUARD_ALLOW": "pytest*",
                                          "TEST_SCOPE_GUARD_DENY": "pytest*"}):
            self.assertEqual(decision(decide("Bash", {"command": "pytest -q"})), "deny")
        with mock.patch.dict(os.environ, {"TEST_SCOPE_GUARD_DENY": "Write"}):
            self.assertEqual(decision(decide("Write", {"file_path": "tests/test_a.py"})), "deny")


class TestScoping(unittest.TestCase):
    SCOPE = {"TEST_SCOPE_GUARD_AGENTS": "*test-writer"}

    def test_matching_agent_is_enforced(self):
        with mock.patch.dict(os.environ, self.SCOPE):
            self.assertEqual(decision(decide("Write", {"file_path": "src/a.py"})), "deny")
            self.assertEqual(decision(decide("Write", {"file_path": "src/a.py"},
                                             agent="test-writer")), "deny")

    def test_other_agent_is_not_enforced(self):
        with mock.patch.dict(os.environ, self.SCOPE):
            self.assertIsNone(decide("Write", {"file_path": "src/a.py"},
                                     agent="four-pass-review:correctness-reviewer"))
            self.assertIsNone(decide("Bash", {"command": "rm -rf x"}, agent="general-purpose"))

    def test_no_identity_defers(self):
        with mock.patch.dict(os.environ, self.SCOPE):
            self.assertIsNone(decide("Write", {"file_path": "src/a.py"}, agent=None))
            self.assertIsNone(decide("Write", {"file_path": "src/a.py"}, agent="  "))

    def test_strict_denies_without_identity(self):
        with mock.patch.dict(os.environ, dict(self.SCOPE, TEST_SCOPE_GUARD_STRICT="1")):
            self.assertEqual(decision(decide("Write", {"file_path": "src/a.py"}, agent=None)),
                             "deny")

    def test_alternate_identity_keys(self):
        with mock.patch.dict(os.environ, self.SCOPE):
            for key in ("agent_name", "subagent_type", "agentType", "subagentType", "sub_agent_name"):
                with self.subTest(key=key):
                    payload = {"tool_name": "Write", "tool_input": {"file_path": "src/a.py"},
                               "cwd": CWD, key: AGENT}
                    self.assertEqual(decision(guard.decide(payload)), "deny")

    def test_unset_scope_enforces_for_everyone(self):
        with mock.patch.dict(os.environ, {"TEST_SCOPE_GUARD_AGENTS": ""}):
            self.assertEqual(decision(decide("Write", {"file_path": "src/a.py"}, agent=None)),
                             "deny")


class TestProcess(unittest.TestCase):
    def run_guard(self, stdin: str, **env) -> tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, GUARD], input=stdin, capture_output=True, text=True,
            env=dict(os.environ, TEST_SCOPE_GUARD_AGENTS="*test-writer", **env))
        return proc.returncode, proc.stdout

    def test_prints_a_decision(self):
        code, out = self.run_guard(json.dumps({
            "tool_name": "Write", "tool_input": {"file_path": "src/a.py"},
            "agent_type": AGENT, "cwd": CWD}))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_prints_nothing_when_deferring(self):
        code, out = self.run_guard(json.dumps({
            "tool_name": "Read", "tool_input": {"file_path": "src/a.py"}, "agent_type": AGENT}))
        self.assertEqual((code, out), (0, ""))

    def test_malformed_payload_fails_closed(self):
        code, out = self.run_guard("not json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_selftest_passes(self):
        proc = subprocess.run(
            [sys.executable, GUARD, "--selftest"], capture_output=True, text=True,
            env=dict(os.environ, TEST_SCOPE_GUARD_AGENTS="*test-writer"))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("selftest: passed", proc.stdout)


if __name__ == "__main__":
    unittest.main()
