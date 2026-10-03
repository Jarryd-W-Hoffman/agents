#!/usr/bin/env python3
"""PreToolUse guard that keeps the test-writer agent inside the test tree.

The mirror of fourpass's read-only guard: that one lets a reviewer
read anything and write nothing; this one lets a test writer add tests and run
them, and nothing else. Reads the PreToolUse hook payload on stdin and prints a
permission decision:

  allow  edits whose every path is a test path (Write only to a path that does
         not exist yet; existing test files are extended with Edit); shell
         commands that are reads or recognised test runners.
  deny   edits to anything else (production source, config, docs), a Write over
         an existing file, any shell
         command that is not on the allow-list, any output redirect to a file,
         process or command substitution, and every MCP tool.
  (none) any other built-in tool is left to the normal permission flow.

The guard fails closed: a command it cannot parse or classify is denied, and
the reason tells the agent what to do instead (report the gap, not fix it).

What it does not do: a test runner executes the project's own test suite,
which can do anything the project's code can. The guard constrains the agent's
tool calls, not the code those calls run.

Configuration (optional, environment variables, comma-separated globs):
  TEST_SCOPE_GUARD_AGENTS   if set, only enforce when the calling agent's type
                            matches one of these globs (hooks.json sets it so
                            other agents and the main session are untouched)
  TEST_SCOPE_GUARD_PATHS    extra repo-relative path globs that count as test
                            paths, e.g. 'src/**/__snapshots__/*,qa/*'
  TEST_SCOPE_GUARD_RUNNERS  extra shell commands to allow as test runners,
                            matched as globs against each simple command
  TEST_SCOPE_GUARD_ALLOW    extra tool names or shell commands to allow
  TEST_SCOPE_GUARD_DENY     extra tool names or shell commands to deny (wins)
  TEST_SCOPE_GUARD_STRICT   "1" denies calls whose payload carries no agent
                            identity at all, instead of deferring
  TEST_SCOPE_GUARD_DEBUG    "1" reports on stderr when a scope is set but the
                            payload names no agent

Run `test-scope-guard.py --selftest` to check the wiring end to end.

Standard library only; no third-party dependencies.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import sys

PREFIX = "test-writer scope: "


# --------------------------------------------------------------------------
# Decision shape and shared helpers
# --------------------------------------------------------------------------

def deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": PREFIX + reason,
        }
    }


def allow(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": PREFIX + reason,
        }
    }


def _globs(env_name: str) -> list[str]:
    raw = os.environ.get(env_name, "")
    return [g.strip() for g in raw.split(",") if g.strip()]


def _matches_any(value: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(value, g) for g in globs)


# --------------------------------------------------------------------------
# Agent identity (copied from the read-only guard; the two plugins must not
# import from each other, because an install carries only one of them)
# --------------------------------------------------------------------------

AGENT_KEYS = ("agent_type", "agent_name", "subagent_type", "agentType", "subagentType")
AGENT_KEY_RE = re.compile(r"^(sub[_-]?)?agent[_-]?(type|name)$", re.I)


def _agent_identity(payload: dict) -> str | None:
    """The calling agent's type/name, or None when the payload names no agent."""
    for key in AGENT_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    for key, value in payload.items():
        if AGENT_KEY_RE.match(key) and isinstance(value, str) and value.strip():
            return value
    return None


# --------------------------------------------------------------------------
# Paths: what counts as a test file
# --------------------------------------------------------------------------

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")

# A directory segment that marks everything beneath it as test code.
TEST_DIRS = frozenset({
    "test", "tests", "__tests__", "spec", "specs", "testing", "test_utils",
    "features",  # cucumber / behave
})

# A file name that marks the file as a test wherever it sits.
TEST_BASENAMES = (
    "test_*.py", "*_test.py", "conftest.py",
    "*_test.go",
    "*.test.js", "*.test.jsx", "*.test.ts", "*.test.tsx", "*.test.mjs", "*.test.cjs",
    "*.spec.js", "*.spec.jsx", "*.spec.ts", "*.spec.tsx", "*.spec.mjs",
    "*Test.php", "*Test.java", "*Tests.cs", "*Test.kt", "*Spec.kt", "*Spec.scala",
    "*_spec.rb", "*_test.rb", "*_test.dart", "*_test.exs", "*.feature",
)


def _relative_to_cwd(path: str, cwd: str) -> str | None:
    """The path relative to cwd after resolving symlinks, or None if it escapes.

    realpath is used on both sides so `tests/../src/app.py` and a symlink
    inside the test tree that points out of it are both seen for what they
    are. The file need not exist yet: realpath resolves whatever prefix does.
    """
    root = os.path.realpath(cwd)
    full = path if os.path.isabs(path) else os.path.join(root, path)
    full = os.path.realpath(full)
    if full == root:
        return None
    if not full.startswith(root.rstrip(os.sep) + os.sep):
        return None
    return os.path.relpath(full, root)


def is_test_path(path: str, cwd: str) -> bool:
    """True when `path` is somewhere the test writer may write."""
    rel = _relative_to_cwd(path, cwd)
    if rel is None:
        return False
    rel = rel.replace(os.sep, "/")
    if _matches_any(rel, _globs("TEST_SCOPE_GUARD_PATHS")):
        return True
    parts = rel.split("/")
    if any(p in TEST_DIRS for p in parts[:-1]):
        return True
    return _matches_any(parts[-1], list(TEST_BASENAMES))


def _edit_paths(tool_input: dict) -> list[str]:
    """Every path an edit-style tool call would touch."""
    out = []
    for key in ("file_path", "notebook_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            out.append(value)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict):
                value = edit.get("file_path")
                if isinstance(value, str) and value.strip():
                    out.append(value)
    return out


def _exists_under_cwd(path: str, cwd: str) -> bool:
    """Whether `path`, resolved the way is_test_path resolves it, already exists."""
    root = os.path.realpath(cwd)
    full = path if os.path.isabs(path) else os.path.join(root, path)
    return os.path.exists(os.path.realpath(full))


def classify_edit(tool_name: str, tool_input: dict, cwd: str) -> tuple[str, str]:
    paths = _edit_paths(tool_input)
    if not paths:
        return "deny", f"`{tool_name}` call names no path; cannot confirm it is a test file"
    for path in paths:
        if not is_test_path(path, cwd):
            return "deny", (f"`{path}` is not a test path; add tests under a test directory "
                            "or report the gap instead of editing source")
    # Write replaces the whole file. Two writers covering the same module both
    # creating tests/billing/test_exporter.py meant the second silently erased
    # the first, so a whole-file write may only create; existing files are
    # extended with Edit.
    if tool_name == "Write":
        for path in paths:
            if _exists_under_cwd(path, cwd):
                return "deny", (f"`{path}` exists; extend it with Edit, never rewrite an "
                                "existing test file")
    return "allow", f"`{paths[0]}` is a test path"


# --------------------------------------------------------------------------
# Shell: reads and test runners only
# --------------------------------------------------------------------------

# Every output redirect form: `>`, `>>`, `&>`, `&>>`, `N>`, `N>>`, `>&`.
REDIRECT_RE = re.compile(r"(?<!<)(?:\d*|&)>{1,2}(&?)\s*([^\s|&;()]*)")
QUOTED_RE = re.compile(r"(?<!\\)'[^']*'|(?<!\\)\"(?:[^\"\\]|\\.)*\"")
SAFE_REDIRECT_RE = re.compile(r"(?:\d*|&)>{1,2}(?:&\d+|\s*/dev/null)")
PROCESS_SUBST_RE = re.compile(r"[<>]\(")
COMMAND_SUBST_RE = re.compile(r"\$\(|`")
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

SEPARATORS = frozenset({"&&", "||", ";", "|", "(", ")", "&", ";;"})
WRAPPERS = frozenset({"env", "nice", "time", "nohup"})

READ_COMMANDS = frozenset({
    "ls", "cat", "head", "tail", "wc", "grep", "rg", "which", "pwd", "echo", "cd",
    "true", "false", ":", "test", "[", "sort", "uniq", "cut", "tr", "diff", "stat",
    "file", "basename", "dirname", "realpath", "printf",
})
FIND_DENIED_FLAGS = ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint",
                     "-fprint0", "-fprintf", "-fls")

GIT_READ_SUBCOMMANDS = frozenset({
    "diff", "log", "show", "status", "grep", "ls-files", "ls-tree", "rev-parse",
    "blame", "merge-base", "cat-file", "describe", "shortlog", "name-rev",
})
GIT_BRANCH_READ_FLAGS = frozenset({"--show-current", "--list", "-a", "--all", "-r",
                                   "--remotes", "-v", "-vv", "--verbose", "--contains",
                                   "--merged", "--no-merged", "--format"})
GIT_GLOBAL_WITH_ARG = frozenset({"-C", "-c", "--git-dir", "--work-tree"})

PYTHONS = re.compile(r"^python(3(\.\d+)?)?$")
TEST_MODULES = frozenset({"pytest", "unittest"})

# Runner families: first word -> rule. Each rule is a function of the
# remaining args returning True when the invocation is a test run.
def _is_npm_test(args: list[str]) -> bool:
    if not args:
        return False
    if args[0] in ("test", "t"):
        return True
    return args[0] == "run" and len(args) > 1 and args[1].startswith("test")


def _is_yarn_test(args: list[str]) -> bool:
    if not args:
        return False
    if args[0] in ("test", "jest", "vitest", "mocha"):
        return True
    return args[0] == "run" and len(args) > 1 and args[1].startswith("test")


def _is_npx_test(args: list[str]) -> bool:
    if not args:
        return False
    if args[0] in ("jest", "vitest", "mocha"):
        return True
    return args[0] == "playwright" and len(args) > 1 and args[1] == "test"


def _first_arg_is(*words: str):
    def check(args: list[str]) -> bool:
        return bool(args) and args[0] in words
    return check


def _make_test(args: list[str]) -> bool:
    targets = [a for a in args if not a.startswith("-") and "=" not in a]
    return bool(targets) and all(t == "test" or t.startswith("test") for t in targets)


RUNNERS = {
    "pytest": lambda args: True,
    "py.test": lambda args: True,
    "npm": _is_npm_test,
    "pnpm": _is_yarn_test,
    "yarn": _is_yarn_test,
    "npx": _is_npx_test,
    "go": _first_arg_is("test"),
    "cargo": _first_arg_is("test"),
    "mvn": _first_arg_is("test", "verify"),
    "gradle": _first_arg_is("test"),
    "./gradlew": _first_arg_is("test"),
    "gradlew": _first_arg_is("test"),
    "dotnet": _first_arg_is("test"),
    "phpunit": lambda args: True,
    "vendor/bin/phpunit": lambda args: True,
    "vendor/bin/pest": lambda args: True,
    "php": lambda args: args[:2] == ["artisan", "test"],
    "rspec": lambda args: True,
    "bundle": lambda args: args[:2] == ["exec", "rspec"],
    "bin/rails": _first_arg_is("test"),
    "mix": _first_arg_is("test"),
    "swift": _first_arg_is("test"),
    "dart": _first_arg_is("test"),
    "flutter": _first_arg_is("test"),
    "ctest": lambda args: True,
    "make": _make_test,
    "deno": _first_arg_is("test"),
    "bun": _first_arg_is("test"),
}


def _strip_quotes(command: str) -> str:
    return QUOTED_RE.sub("", command)


def _has_file_redirect(command: str) -> str | None:
    for m in REDIRECT_RE.finditer(_strip_quotes(command)):
        dup, target = m.group(1), m.group(2)
        if dup == "&" and re.fullmatch(r"\d+", target):
            continue  # `2>&1`, `>&2`
        if not dup and target == "/dev/null":
            continue  # `2>/dev/null`, `&>/dev/null`
        return m.group(0).strip()
    return None


def _simple_commands(command: str) -> list[list[str]]:
    """Split a shell line into its simple commands' argv lists.

    shlex with punctuation_chars keeps `&&`, `||`, `;`, `|`, `(` and `)` as
    their own tokens, so the split respects quoting: `pytest -k "a and b"` is
    one command, not three.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    tokens = list(lexer)
    out: list[list[str]] = []
    current: list[str] = []
    for tok in tokens:
        if tok in SEPARATORS:
            if current:
                out.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        out.append(current)
    return out


def _unwrap(argv: list[str]) -> list[str]:
    """Drop leading VAR=value assignments and wrappers such as env and timeout."""
    i = 0
    while i < len(argv):
        tok = argv[i]
        if ASSIGNMENT_RE.match(tok):
            i += 1
        elif tok in WRAPPERS:
            i += 1
            # `env -i`, `nice -n 10`: skip the wrapper's own flags.
            while i < len(argv) and argv[i].startswith("-"):
                i += 1 if argv[i] not in ("-n", "-u") else 2
        elif tok == "timeout":
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 2 if argv[i] in ("-s", "-k", "--signal", "--kill-after") else 1
            i += 1  # the duration
        else:
            break
    return argv[i:]


def _is_git_read(args: list[str]) -> bool:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] in GIT_GLOBAL_WITH_ARG:
            i += 2
        else:
            i += 1
    if i >= len(args):
        return False
    sub, rest = args[i], args[i + 1:]
    if sub in GIT_READ_SUBCOMMANDS:
        return True
    if sub == "branch":
        return all(a.startswith("-") and a.split("=")[0] in GIT_BRANCH_READ_FLAGS
                   for a in rest) or not rest
    return False


def _is_python_test(args: list[str]) -> bool:
    if "-c" in args:
        return False
    for i, a in enumerate(args):
        if a == "-m":
            return i + 1 < len(args) and args[i + 1] in TEST_MODULES
        if not a.startswith("-"):
            return False
    return False


def _classify_simple(argv: list[str]) -> tuple[str, str]:
    argv = _unwrap(argv)
    if not argv:
        return "allow", "empty command"
    joined = " ".join(argv)
    cmd, args = argv[0], argv[1:]
    if _matches_any(joined, _globs("TEST_SCOPE_GUARD_RUNNERS")):
        return "allow", f"`{cmd}` is allowed by TEST_SCOPE_GUARD_RUNNERS"
    if args in (["--version"], ["-V"], ["version"]):
        return "allow", f"`{joined}` is a version check"
    if cmd == "git":
        if _is_git_read(args):
            return "allow", f"`git {args[0] if args else ''}` is a read"
        return "deny", (f"`{joined[:80]}` changes repository state; the test writer "
                        "never commits, stages or switches branches")
    if cmd == "find":
        if any(a in FIND_DENIED_FLAGS for a in args):
            return "deny", f"`find` with an action flag can modify files; list paths only"
        return "allow", "`find` without actions is a read"
    if cmd in READ_COMMANDS:
        return "allow", f"`{cmd}` is a read"
    if PYTHONS.match(cmd):
        if _is_python_test(args):
            return "allow", f"`{joined[:80]}` runs the test suite"
        return "deny", (f"`{joined[:80]}` is not a test run; only `python -m pytest` and "
                        "`python -m unittest` are allowed")
    rule = RUNNERS.get(cmd)
    if rule is not None and rule(args):
        return "allow", f"`{joined[:80]}` runs the test suite"
    return "deny", (f"`{joined[:80]}` is not a read or a recognised test runner; "
                    "set TEST_SCOPE_GUARD_RUNNERS to allow another runner")


def classify_bash(command: str) -> tuple[str, str]:
    """('allow'|'deny', reason) for a whole shell line."""
    if not command.strip():
        return "allow", "empty command"
    unquoted = _strip_quotes(command)
    redirect = _has_file_redirect(command)
    if redirect:
        return "deny", f"`{redirect}` writes to a file; tests go through Write or Edit"
    if PROCESS_SUBST_RE.search(unquoted):
        return "deny", "process substitution is not allowed"
    if COMMAND_SUBST_RE.search(unquoted):
        return "deny", "command substitution is not allowed; run the command on its own"
    try:
        commands = _simple_commands(SAFE_REDIRECT_RE.sub(" ", command))
    except ValueError as e:
        return "deny", f"could not parse the command ({e})"
    reasons = []
    for argv in commands:
        verdict, reason = _classify_simple(argv)
        if verdict == "deny":
            return "deny", reason
        reasons.append(reason)
    return "allow", "; ".join(reasons) if reasons else "empty command"


# --------------------------------------------------------------------------
# The decision
# --------------------------------------------------------------------------

def decide(payload: dict) -> dict | None:
    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd") or os.getcwd()

    scope = _globs("TEST_SCOPE_GUARD_AGENTS")
    if scope:
        agent = _agent_identity(payload)
        if agent is None:
            # No agent identity: the main session, or a renamed envelope key.
            # Denying here would break the user's own tools, so defer unless
            # STRICT opts into failing closed. See the read-only guard for why.
            if os.environ.get("TEST_SCOPE_GUARD_STRICT") == "1":
                return deny("no agent identity in the hook payload and "
                            "TEST_SCOPE_GUARD_STRICT=1; cannot confirm this is not the test writer")
            if os.environ.get("TEST_SCOPE_GUARD_DEBUG") == "1":
                print(f"test-scope-guard: scope {scope} is set but the payload carries no "
                      f"agent identity (keys: {sorted(payload)}); not enforcing",
                      file=sys.stderr)
            return None
        if not _matches_any(agent, scope):
            return None

    subject = tool_name
    if tool_name == "Bash":
        subject = tool_input.get("command", "") or ""

    if _matches_any(tool_name, _globs("TEST_SCOPE_GUARD_DENY")) or (
            tool_name == "Bash" and _matches_any(subject, _globs("TEST_SCOPE_GUARD_DENY"))):
        return deny(f"`{subject[:80]}` is denied by TEST_SCOPE_GUARD_DENY")
    if _matches_any(tool_name, _globs("TEST_SCOPE_GUARD_ALLOW")) or (
            tool_name == "Bash" and _matches_any(subject, _globs("TEST_SCOPE_GUARD_ALLOW"))):
        return allow("allowed by TEST_SCOPE_GUARD_ALLOW")

    if tool_name in EDIT_TOOLS:
        verdict, reason = classify_edit(tool_name, tool_input, cwd)
        return deny(reason) if verdict == "deny" else allow(reason)
    if tool_name == "Bash":
        verdict, reason = classify_bash(subject)
        return deny(reason) if verdict == "deny" else allow(reason)
    if tool_name.startswith("mcp__"):
        return deny(f"`{tool_name}` is an MCP tool; the test writer works from the "
                    "repository alone")
    return None  # other built-ins: defer to the normal permission flow


def selftest() -> int:
    """Check the guard is wired up: scope resolution, path, shell and MCP decisions.

        TEST_SCOPE_GUARD_AGENTS='*test-writer' python3 test-scope-guard.py --selftest
    """
    scope = _globs("TEST_SCOPE_GUARD_AGENTS")
    agent = "testgaps:test-writer"
    if scope and not _matches_any(agent, scope):
        agent = scope[0].replace("*", "x")
    base = {"agent_type": agent, "cwd": "/repo"}
    cases = [
        ("Write", {"file_path": "tests/test_export.py", "content": "x"}, "allow"),
        ("Write", {"file_path": "src/export.py", "content": "x"}, "deny"),
        ("Edit", {"file_path": "/repo/tests/../src/export.py"}, "deny"),
        ("Bash", {"command": "pytest tests/test_export.py -q"}, "allow"),
        ("Bash", {"command": "git diff HEAD --stat"}, "allow"),
        ("Bash", {"command": "rm -rf build"}, "deny"),
        ("Bash", {"command": "pytest -q > out.txt"}, "deny"),
        ("mcp__github__create_issue_comment", {}, "deny"),
    ]
    failures = 0
    for tool_name, tool_input, want in cases:
        result = decide(dict(base, tool_name=tool_name, tool_input=tool_input))
        got = (result or {}).get("hookSpecificOutput", {}).get("permissionDecision", "defer")
        status = "ok" if got == want else "FAIL"
        if got != want:
            failures += 1
        detail = tool_input.get("command") or tool_input.get("file_path") or ""
        print(f"{status}: {tool_name} {detail}".rstrip() + f" -> {got} (want {want})")
    # A Write over an existing test file: use this plugin's own test suite as
    # the existing file, with cwd set to the plugin root so the path resolves.
    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    existing = "tests/test_test_scope_guard.py"
    result = decide(dict(base, cwd=plugin_root, tool_name="Write",
                         tool_input={"file_path": existing, "content": "x"}))
    got = (result or {}).get("hookSpecificOutput", {}).get("permissionDecision", "defer")
    want = "deny" if os.path.exists(os.path.join(plugin_root, existing)) else "allow"
    status = "ok" if got == want else "FAIL"
    if got != want:
        failures += 1
    print(f"{status}: Write {existing} (existing file) -> {got} (want {want})")
    if _agent_identity(base) is None:
        print("FAIL: agent identity not resolved from a payload that carries agent_type")
        failures += 1
    print(f"scope: {scope or '(unset: enforcing for every caller)'}")
    print("selftest: " + ("passed" if not failures else f"{failures} failure(s)"))
    return 0 if not failures else 1


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        return selftest()
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError) as e:  # malformed input: fail closed
        print(json.dumps(deny(f"unreadable hook payload ({e})")))
        return 0
    try:
        result = decide(payload)
    except Exception as e:  # any internal error: fail closed
        result = deny(f"guard error ({e.__class__.__name__}: {e})")
    if result is not None:
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
