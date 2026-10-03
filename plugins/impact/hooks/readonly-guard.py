#!/usr/bin/env python3
"""PreToolUse guard that keeps a plugin's reviewer agents strictly read-only.

Reads the PreToolUse hook payload on stdin and prints a permission decision:

  deny   built-in write tools, any shell command that can change state
         (files, git history, remote systems), and any MCP tool whose name
         looks like a write operation.
  allow  shell commands and MCP tools recognised as read-only, so reviewers
         can inspect GitHub, GitLab, Jira, Linear, etc. without prompting.
  (none) anything else is left to the normal permission flow.

The guard fails closed: a command it cannot parse or classify is denied,
and the reason tells the agent what to use instead.

Configuration (optional, environment variables, comma-separated globs):
  READONLY_GUARD_ALLOW  extra tool names or shell commands to allow
  READONLY_GUARD_DENY   extra tool names or shell commands to deny (wins)
  READONLY_GUARD_AGENTS if set, only enforce when the calling agent's type
                        matches one of these globs (used by the plugin-level
                        hook so it does not affect other agents)
  READONLY_GUARD_STRICT "1" denies calls whose payload carries no agent
                        identity at all, instead of deferring. Off by default,
                        because the main session's own calls look like that.
  READONLY_GUARD_DEBUG  "1" reports on stderr when a scope is set but the
                        payload names no agent, which is what a renamed
                        envelope key would look like.

Run `readonly-guard.py --selftest` to check the wiring end to end.

Standard library only; no third-party dependencies.
"""

from __future__ import annotations

import json
import os
import re
import sys

# The guard is invoked by absolute path from hooks.json and from another
# project's settings.json, and is also imported by the tests without being
# executed as a script. Neither case puts this file's directory on sys.path,
# so the package next to it is not importable until we say so.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from guard.mcp import classify_mcp  # noqa: E402
from guard.shell import classify_bash  # noqa: E402
from guard.tables import DENIED_BUILTIN_TOOLS  # noqa: E402
from guard.util import _globs, _matches_any, allow, deny  # noqa: E402

# Keys the PreToolUse envelope has carried for the calling agent's identity.
# Claude Code 2.1.x sends `agent_type` (and `agent_id`); the others are older or
# adjacent spellings. The regex is the backstop: if the envelope ever renames the
# field, a name shaped like an agent identity is still found, so the guard keeps
# enforcing instead of silently switching itself off.
AGENT_KEYS = ("agent_type", "agent_name", "subagent_type", "agentType", "subagentType")
AGENT_KEY_RE = re.compile(r"^(sub[_-]?)?agent[_-]?(type|name)$", re.I)


def _agent_identity(payload: dict) -> str | None:
    """The calling agent's type/name, or None when the payload names no agent.

    None means "this is not an agent call, or the envelope changed shape" --
    the caller decides what to do about it. An empty string is not returned:
    a key present but blank is treated as absent.
    """
    for key in AGENT_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    for key, value in payload.items():
        if AGENT_KEY_RE.match(key) and isinstance(value, str) and value.strip():
            return value
    return None


def decide(payload: dict) -> dict | None:
    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}

    scope = _globs("READONLY_GUARD_AGENTS")
    if scope:
        agent = _agent_identity(payload)
        if agent is None:
            # No agent-identifying key at all. Normal for the main session, which
            # this guard is not meant to touch -- but it is also what a renamed
            # envelope key would look like, and then the guard is silently off.
            # Every other unknown in this file fails closed; this one cannot,
            # because denying the main session would break the user's own tools.
            # READONLY_GUARD_STRICT=1 opts into failing closed anyway, and
            # READONLY_GUARD_DEBUG=1 makes the no-op visible.
            if os.environ.get("READONLY_GUARD_STRICT") == "1":
                return deny("no agent identity in the hook payload and "
                            "READONLY_GUARD_STRICT=1; cannot confirm this is not a reviewer")
            if os.environ.get("READONLY_GUARD_DEBUG") == "1":
                print(f"readonly-guard: scope {scope} is set but the payload carries no "
                      f"agent identity (keys: {sorted(payload)}); not enforcing",
                      file=sys.stderr)
            return None
        if not _matches_any(agent, scope):
            return None

    subject = tool_name
    if tool_name == "Bash":
        subject = tool_input.get("command", "") or ""

    if _matches_any(tool_name, _globs("READONLY_GUARD_DENY")) or (
            tool_name == "Bash" and _matches_any(subject, _globs("READONLY_GUARD_DENY"))):
        return deny(f"`{subject[:80]}` is denied by READONLY_GUARD_DENY")
    if _matches_any(tool_name, _globs("READONLY_GUARD_ALLOW")) or (
            tool_name == "Bash" and _matches_any(subject, _globs("READONLY_GUARD_ALLOW"))):
        return allow("allowed by READONLY_GUARD_ALLOW")

    if tool_name in DENIED_BUILTIN_TOOLS:
        return deny(f"`{tool_name}` modifies files; report findings instead of fixing them")
    if tool_name == "Bash":
        verdict, reason = classify_bash(subject)
        return deny(reason) if verdict == "deny" else allow(reason)
    if tool_name.startswith("mcp__"):
        verdict, reason = classify_mcp(tool_name)
        return deny(reason) if verdict == "deny" else allow(reason)
    return None  # other built-ins: defer to the normal permission flow


def selftest() -> int:
    """Check the guard is wired up: scope resolution, one deny, one allow.

    Run it the way the hook runs it, so a stale `READONLY_GUARD_AGENTS` or an
    envelope that no longer carries an agent identity shows up as a failure
    here instead of as a guard that quietly stops enforcing:

        READONLY_GUARD_AGENTS='*-reviewer' python3 readonly-guard.py --selftest
    """
    scope = _globs("READONLY_GUARD_AGENTS")
    agent = "fourpass:correctness-reviewer"
    if scope and not _matches_any(agent, scope):
        agent = scope[0].replace("*", "x")
    base = {"agent_type": agent}
    cases = [
        ("Bash", {"command": "git diff HEAD"}, "allow"),
        ("Bash", {"command": "rm -rf build"}, "deny"),
        ("Bash", {"command": "echo hi > out.txt"}, "deny"),
        ("Write", {"file_path": "/tmp/x", "content": "y"}, "deny"),
        ("mcp__github__get_pull_request", {}, "allow"),
        ("mcp__github__create_issue_comment", {}, "deny"),
    ]
    failures = 0
    for tool_name, tool_input, want in cases:
        result = decide(dict(base, tool_name=tool_name, tool_input=tool_input))
        got = (result or {}).get("hookSpecificOutput", {}).get("permissionDecision", "defer")
        status = "ok" if got == want else "FAIL"
        if got != want:
            failures += 1
        print(f"{status}: {tool_name} {tool_input.get('command', '')}".rstrip()
              + f" -> {got} (want {want})")
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
    except Exception as e:  # malformed input: fail closed
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
