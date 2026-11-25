#!/usr/bin/env python3
"""PreToolUse guard that keeps the manual-writer agent inside the docs tree.

A manual writer reads the code and writes one chapter of the user manual. It
needs to read anything and write Markdown under docs/, and nothing else.
Reads the PreToolUse hook payload on stdin and prints a permission decision:

  allow  Edit and Write whose path is a Markdown file under one of the docs
         directories, inside the repository.
  deny   Edit and Write anywhere else (source, config, the README, images),
         MultiEdit and NotebookEdit, every shell command, and every MCP tool.
  (none) any other built-in tool (Read, Grep, Glob) is left to the normal
         permission flow.

The guard fails closed: a payload it cannot read, or an internal error, is a
deny with a reason that tells the agent what to do instead.

The lead, not the writer, runs the app and takes the screenshots, so the
writer never needs a shell.

Configuration (optional, environment variables, comma-separated):
  DOCS_SCOPE_GUARD_AGENTS   if set, only enforce when the calling agent's type
                            matches one of these globs (hooks.json sets it, so
                            other agents and the main session are untouched)
  DOCS_SCOPE_GUARD_DIRS     repository-relative directories the writer may
                            write Markdown in (default: docs)
  DOCS_SCOPE_GUARD_STRICT   "1" denies calls whose payload names no agent,
                            instead of deferring

Run `docs-scope-guard.py --selftest` to check the wiring end to end.

Standard library only; runs on Python 3.9.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys

PREFIX = "manual-writer scope: "
EDIT_TOOLS = ("Edit", "Write")
NEVER_TOOLS = ("MultiEdit", "NotebookEdit", "Bash", "BashOutput", "KillShell", "WebFetch",
               "WebSearch")

# Copied from the read-only guard; plugins must not import from each other.
AGENT_KEYS = ("agent_type", "agent_name", "subagent_type", "agentType", "subagentType")
AGENT_KEY_RE = re.compile(r"^(sub[_-]?)?agent[_-]?(type|name)$", re.I)


def deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": PREFIX + reason}}


def allow(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                   "permissionDecisionReason": PREFIX + reason}}


def _list(env_name: str, default: str = "") -> list[str]:
    raw = os.environ.get(env_name, default)
    return [g.strip() for g in raw.split(",") if g.strip()]


def _agent_identity(payload: dict) -> str | None:
    for key in AGENT_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    for key, value in payload.items():
        if AGENT_KEY_RE.match(key) and isinstance(value, str) and value.strip():
            return value
    return None


def classify_path(path: str, cwd: str) -> tuple[str, str]:
    if not path:
        return "deny", "no file_path given"
    full = os.path.normpath(path if os.path.isabs(path) else os.path.join(cwd, path))
    rel = os.path.relpath(full, os.path.normpath(cwd))
    if rel == ".." or rel.startswith(".." + os.sep) or os.path.isabs(rel):
        return "deny", f"`{path}` is outside the repository"
    if not rel.lower().endswith(".md"):
        return "deny", (f"`{rel}` is not a Markdown file; the writer writes its chapter, "
                        "and the lead takes screenshots and edits everything else")
    rel_posix = rel.replace(os.sep, "/")
    for d in _list("DOCS_SCOPE_GUARD_DIRS", "docs"):
        d = d.strip("/")
        if rel_posix.startswith(d + "/"):
            return "allow", f"`{rel_posix}` is in {d}/"
    return "deny", (f"`{rel_posix}` is not under "
                    f"{', '.join(d + '/' for d in _list('DOCS_SCOPE_GUARD_DIRS', 'docs'))}; "
                    "report what else should change instead of changing it")


def decide(payload: dict) -> dict | None:
    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd") or os.getcwd()

    scope = _list("DOCS_SCOPE_GUARD_AGENTS")
    if scope:
        agent = _agent_identity(payload)
        if agent is None:
            if os.environ.get("DOCS_SCOPE_GUARD_STRICT") == "1":
                return deny("no agent identity in the hook payload and DOCS_SCOPE_GUARD_STRICT=1")
            return None
        if not any(fnmatch.fnmatchcase(agent, g) for g in scope):
            return None

    if tool_name in EDIT_TOOLS:
        verdict, reason = classify_path(str(tool_input.get("file_path", "") or ""), cwd)
        return deny(reason) if verdict == "deny" else allow(reason)
    if tool_name in NEVER_TOOLS:
        return deny(f"`{tool_name}` is not available to the writer; read with Read, Grep and "
                    "Glob, write the chapter with Write or Edit, and list anything else in "
                    "your reply for the lead")
    if tool_name.startswith("mcp__"):
        return deny(f"`{tool_name}` is an MCP tool; the writer works from the repository alone")
    return None


def selftest() -> int:
    """DOCS_SCOPE_GUARD_AGENTS='*manual-writer' python3 docs-scope-guard.py --selftest"""
    scope = _list("DOCS_SCOPE_GUARD_AGENTS")
    agent = "docs:manual-writer"
    if scope and not any(fnmatch.fnmatchcase(agent, g) for g in scope):
        agent = scope[0].replace("*", "x")
    base = {"agent_type": agent, "cwd": "/repo"}
    cases = [
        ("Write", {"file_path": "docs/manual/04-links.md"}, "allow"),
        ("Edit", {"file_path": "/repo/docs/manual/README.md"}, "allow"),
        ("Write", {"file_path": "README.md"}, "deny"),
        ("Write", {"file_path": "docs/manual/images/x.png"}, "deny"),
        ("Edit", {"file_path": "/repo/docs/../app/Models/Note.php"}, "deny"),
        ("Write", {"file_path": "/elsewhere/docs/a.md"}, "deny"),
        ("Bash", {"command": "ls"}, "deny"),
        ("MultiEdit", {"file_path": "docs/manual/04-links.md"}, "deny"),
        ("mcp__github__create_issue", {}, "deny"),
        ("Read", {"file_path": "app/Models/Note.php"}, "defer"),
    ]
    failures = 0
    for tool_name, tool_input, want in cases:
        result = decide(dict(base, tool_name=tool_name, tool_input=tool_input))
        got = (result or {}).get("hookSpecificOutput", {}).get("permissionDecision", "defer")
        if got != want:
            failures += 1
        detail = tool_input.get("command") or tool_input.get("file_path") or ""
        print(f"{'ok' if got == want else 'FAIL'}: {tool_name} {detail}".rstrip()
              + f" -> {got} (want {want})")
    if scope:
        other = decide({"agent_type": "someone-else", "cwd": "/repo", "tool_name": "Bash",
                        "tool_input": {"command": "ls"}})
        if other is not None:
            failures += 1
            print("FAIL: an agent outside the scope was not left alone")
        else:
            print("ok: an agent outside the scope is left alone")
    print(f"scope: {scope or '(unset: enforcing for every caller)'}")
    print("selftest: " + ("passed" if not failures else f"{failures} failure(s)"))
    return 0 if not failures else 1


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        return selftest()
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError) as e:
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
