"""The allow/deny decision shape, and helpers shared by the classifiers.

Part of the read-only guard. The entry point is `hooks/readonly-guard.py`;
this module is not meant to be run directly.
"""

from __future__ import annotations

import fnmatch
import os
import re


def deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"read-only reviewer: {reason}",
        }
    }


def allow(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": f"read-only reviewer: {reason}",
        }
    }


def _globs(env_name: str) -> list[str]:
    raw = os.environ.get(env_name, "")
    return [g.strip() for g in raw.split(",") if g.strip()]


def _matches_any(value: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(value, g) for g in globs)


def _ordered_tokens_of_name(name: str) -> list[str]:
    """Split an MCP tool name into lowercase words (snake, kebab, camel)."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return [t for t in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if t]
