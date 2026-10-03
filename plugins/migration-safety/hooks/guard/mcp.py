"""MCP tool-name classification: does this tool name look like a write?

Part of the read-only guard. The entry point is `hooks/readonly-guard.py`;
this module is not meant to be run directly.
"""

from __future__ import annotations

from .tables import *  # noqa: F401,F403
from .util import _ordered_tokens_of_name


def classify_mcp(tool_name: str) -> tuple[str, str]:
    parts = tool_name.split("__")
    tool = parts[-1] if len(parts) >= 3 else tool_name
    normalised = tool
    for pattern, replacement in MCP_COMPOUND_NOUNS:
        normalised = pattern.sub(replacement, normalised)
    ordered = _ordered_tokens_of_name(normalised)
    tokens = set(ordered)
    write_hits = tokens & MCP_STRONG_WRITE
    if write_hits:
        return "deny", f"MCP tool `{tool_name}` looks like a write operation (`{sorted(write_hits)[0]}`)"
    if ordered and ordered[0] in MCP_READ_HEADS:
        return "allow", f"MCP tool `{tool_name}` is a read operation"
    if tokens & MCP_READ_HEADS:
        return "allow", f"MCP tool `{tool_name}` is a read operation"
    return "deny", (f"MCP tool `{tool_name}` could not be classified as read-only; "
                    "prefer a get/list/search/read tool, or set READONLY_GUARD_ALLOW")
