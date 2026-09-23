#!/usr/bin/env python3
"""PreToolUse guard that keeps the four-pass-review agents strictly read-only.

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

Standard library only; no third-party dependencies.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import sys

# --------------------------------------------------------------------------
# Built-in tools
# --------------------------------------------------------------------------

DENIED_BUILTIN_TOOLS = {
    "Edit", "Write", "MultiEdit", "NotebookEdit", "ExitPlanMode",
}

# --------------------------------------------------------------------------
# Shell commands
# --------------------------------------------------------------------------

# Plain read-only utilities. Some have per-command flag checks below.
READONLY_COMMANDS = {
    "ls", "cat", "head", "tail", "less", "more", "wc", "grep", "egrep",
    "fgrep", "rg", "ag", "ack", "find", "fd", "tree", "file", "stat", "du",
    "df", "diff", "cmp", "comm", "sort", "uniq", "cut", "tr", "awk", "jq",
    "yq", "echo", "printf", "true", "false", "test", "[", "pwd", "which",
    "type", "whoami", "id", "date", "env", "printenv", "basename",
    "dirname", "realpath", "readlink", "md5sum", "shasum", "sha256sum",
    "strings", "column", "paste", "nl", "tac", "rev", "seq", "sleep",
    "hostname", "uname", "xxd", "hexdump", "od", "expr", "bc", "tput",
    "man", "help", "sed",
}

# Wrappers that run another command; unwrap and inspect the inner command.
WRAPPER_COMMANDS = {"time", "command", "nice", "ionice", "caffeinate"}

# Explicitly denied even though some look harmless.
DENIED_COMMANDS = {
    "rm", "mv", "cp", "touch", "mkdir", "rmdir", "chmod", "chown", "chgrp",
    "ln", "dd", "tee", "truncate", "install", "rsync", "scp", "sftp",
    "sudo", "su", "doas", "eval", "exec", "source", ".", "xargs", "nohup",
    "bash", "sh", "zsh", "fish", "dash", "ksh", "python", "python3", "node",
    "php", "ruby", "perl", "deno", "bun", "npm", "npx", "pnpm", "yarn",
    "composer", "pip", "pip3", "make", "cargo", "go", "mvn", "gradle",
    "docker", "docker-compose", "kubectl", "helm", "terraform", "ansible",
    "psql", "mysql", "sqlite3", "redis-cli", "mongo", "mongosh", "artisan",
    "kill", "killall", "pkill", "reboot", "shutdown", "crontab", "at",
    "open", "xdg-open", "pbcopy", "osascript", "ssh", "telnet", "nc",
    "ncat", "socat", "mail", "sendmail",
}

# git subcommands that never change the working tree, index, refs or config.
GIT_READONLY = {
    "status", "log", "diff", "show", "blame", "rev-parse", "rev-list",
    "ls-files", "ls-tree", "ls-remote", "cat-file", "grep", "shortlog",
    "describe", "merge-base", "name-rev", "for-each-ref", "count-objects",
    "check-ignore", "check-attr", "diff-tree", "diff-index", "diff-files",
    "whatchanged", "reflog", "var", "version", "help", "range-diff",
    "cherry", "show-ref", "show-branch", "verify-commit", "verify-tag",
    "fsck",
}
# git subcommands that are read-only only with these argument shapes.
GIT_CONDITIONAL = {
    # branch: listing only (no positional args that would create/delete)
    "branch": {"deny_flags": {"-d", "-D", "-m", "-M", "-c", "-C", "--delete",
                              "--move", "--copy", "--set-upstream-to", "-u",
                              "--unset-upstream", "--edit-description"},
               "allow_positional": False},
    "tag": {"deny_flags": {"-a", "-d", "-f", "-s", "-m", "-F", "--delete",
                           "--annotate", "--sign", "--force"},
            "allow_positional": False},
    "remote": {"allow_sub": {"-v", "--verbose", "show", "get-url"}},
    "stash": {"allow_sub": {"list", "show"}},
    "worktree": {"allow_sub": {"list"}},
    "notes": {"allow_sub": {"show", "list"}},
    "config": {"require_any": {"--get", "--get-all", "--get-regexp", "--list",
                               "-l", "--show-origin", "--show-scope"}},
    "symbolic-ref": {"max_positional": 1},
    # fetch updates remote-tracking refs only; needed to review PR branches.
    "fetch": {"allow_all": True},
    "submodule": {"allow_sub": {"status", "summary"}},
    "bisect": {"allow_sub": {"log", "visualize", "view"}},
}

# gh / glab subcommand trees: verb allowlists per noun.
GH_READONLY = {
    "pr": {"view", "diff", "list", "checks", "status"},
    "issue": {"view", "list", "status"},
    "repo": {"view", "list"},
    "run": {"view", "list", "watch"},
    "workflow": {"view", "list"},
    "release": {"view", "list"},
    "label": {"list"},
    "search": {"repos", "issues", "prs", "commits", "code"},
    "gist": {"view", "list"},
    "auth": {"status"},
    "codespace": {"list"},
    "project": {"view", "list", "item-list", "field-list"},
    "cache": {"list"},
    "ruleset": {"view", "list"},
    "secret": {"list"},
    "variable": {"list"},
    "status": set(),
    "api": set(),  # handled by _check_api_call
}
GLAB_READONLY = {
    "mr": {"view", "diff", "list"},
    "issue": {"view", "list"},
    "repo": {"view", "list"},
    "ci": {"view", "status", "list", "trace", "get"},
    "release": {"view", "list"},
    "label": {"list"},
    "variable": {"list"},
    "auth": {"status"},
    "api": set(),
}
API_WRITE_FLAGS = {"-X", "--method", "-f", "-F", "--field", "--raw-field",
                   "--input", "-d", "--data", "--data-raw", "--data-binary",
                   "--data-urlencode", "-T", "--upload-file", "--form"}

# Generic CLIs (issue trackers, clouds, etc.): allowed when a read verb is
# present and no write verb appears anywhere in the arguments.
GENERIC_CLIS = {
    "jira", "acli", "linear", "lin", "linear-cli", "confluence", "sentry-cli",
    "aws", "az", "gcloud", "doctl", "vercel", "netlify", "heroku", "fly",
    "flyctl", "railway", "stripe", "slack", "trello", "asana", "notion",
    "clickup", "shortcut", "monday", "gh-dash", "tea", "bb", "hub",
    "curl", "wget", "http", "https", "httpie", "xh",
}
READ_VERBS = {
    "view", "list", "ls", "get", "show", "diff", "status", "checks", "search",
    "log", "logs", "cat", "print", "describe", "read", "info", "me", "whoami",
    "version", "help", "query", "find", "fetch", "lookup", "count", "check",
    "history", "browse", "tail", "head", "watch", "trace", "explain",
    "validate", "lint", "test", "dry-run", "preview", "inspect", "retrieve",
    "download", "export",
}
WRITE_VERBS = {
    "create", "new", "add", "edit", "update", "delete", "remove", "rm", "del",
    "comment", "close", "reopen", "merge", "assign", "unassign", "transition",
    "move", "archive", "unarchive", "ready", "review", "approve", "reject",
    "lock", "unlock", "push", "pull", "sync", "set", "put", "post", "patch",
    "publish", "unpublish", "release", "upload", "import", "checkout", "clone",
    "init", "link", "unlink", "vote", "unvote", "start", "stop", "restart",
    "done", "resolve", "submit", "cancel", "rename", "tag", "untag", "label",
    "unlabel", "star", "unstar", "fork", "follow", "unfollow", "subscribe",
    "unsubscribe", "mark", "send", "notify", "trigger", "dispatch", "invoke",
    "execute", "exec", "run", "apply", "deploy", "destroy", "rollback",
    "scale", "restore", "reset", "revert", "clear", "purge", "prune", "kill",
    "attach", "detach", "enable", "disable", "grant", "revoke", "login",
    "logout", "save", "write", "copy", "cp", "mv", "install", "uninstall",
    "upgrade", "downgrade", "bump", "convert", "migrate", "seed", "flush",
    "truncate", "drop", "insert", "replace", "transfer", "dismiss", "request",
    "resend", "invite", "join", "leave", "ban", "unban", "block", "unblock",
    "pin", "unpin", "react", "flag", "unflag", "escalate", "snooze",
    "schedule", "reschedule", "reassign", "relate", "unrelate", "attachment",
}
WRITE_VERBS_CURL = {"-X", "--request", "-d", "--data", "--data-raw",
                    "--data-binary", "--data-urlencode", "-F", "--form",
                    "-T", "--upload-file", "-o", "--output", "-O",
                    "--remote-name", "--post301", "--post302", "--post303"}

# --------------------------------------------------------------------------
# MCP tools
# --------------------------------------------------------------------------

# Verbs that unambiguously change state when they appear anywhere in a tool name.
MCP_STRONG_WRITE = {
    "create", "creates", "add", "adds", "edit", "edits", "update", "updates",
    "delete", "deletes", "remove", "removes", "del", "set", "sets", "put",
    "post", "posts", "patch", "write", "writes", "save", "saves", "send",
    "sends", "push", "transition", "transitions", "assign", "assigns",
    "unassign", "merge", "merges", "close", "closes", "reopen", "approve",
    "reject", "submit", "publish", "unpublish", "upload", "import", "dispatch",
    "trigger", "run", "execute", "exec", "invoke", "deploy", "destroy",
    "archive", "unarchive", "move", "rename", "star", "unstar", "fork",
    "follow", "unfollow", "subscribe", "unsubscribe", "notify", "mark",
    "navigate", "click", "fill", "press", "scroll", "hover", "drag", "type",
    "evaluate", "emulate", "modify", "change", "register", "unregister",
    "provision", "deprovision", "generate", "commit", "amend", "squash",
    "apply", "restore", "reset", "revert", "clear", "purge", "prune", "kill",
    "enable", "disable", "grant", "revoke", "login", "logout", "install",
    "uninstall", "insert", "replace", "drop", "truncate", "flush", "migrate",
    "seed", "invite", "join", "leave", "ban", "unban", "block", "unblock",
    "pin", "unpin", "react", "dismiss", "cancel", "lock", "unlock", "vote",
    "resolve", "unresolve", "snooze", "escalate", "schedule", "reassign",
    "convert", "transfer", "copy", "duplicate", "clone", "init", "link",
    "unlink", "attach", "detach", "reply", "comment", "record", "start",
    "stop", "restart", "pause", "resume", "rollback", "scale", "sync",
    "manage", "configure", "bump", "upgrade", "downgrade",
}
# Read verbs; a tool whose name starts with one of these (and contains no
# strong write verb) is a read.
MCP_READ_HEADS = {
    "get", "gets", "list", "lists", "search", "searches", "read", "reads",
    "fetch", "fetches", "find", "finds", "query", "queries", "show", "shows",
    "view", "views", "describe", "retrieve", "lookup", "look", "count",
    "check", "browse", "download", "export", "inspect", "preview", "diff",
    "compare", "status", "info", "summarize", "summarise", "explain",
    "analyze", "analyse", "validate", "lint", "who", "whoami", "me", "help",
    "version", "history", "log", "logs", "tail", "head", "watch", "trace",
    "ping", "health", "can",
}
# Compound nouns that contain a write-looking word but are not writes.
MCP_COMPOUND_NOUNS = [
    (re.compile(r"pull[_\-]?requests?", re.I), "pullrequest"),
    (re.compile(r"merge[_\-]?requests?", re.I), "mergerequest"),
    (re.compile(r"push[_\-]?events?", re.I), "pushevent"),
    (re.compile(r"commit[_\-]?status(es)?", re.I), "commitstatus"),
    (re.compile(r"run[_\-]?logs?", re.I), "runlog"),
    (re.compile(r"workflow[_\-]?runs?", re.I), "workflowrun"),
    (re.compile(r"(job|check)[_\-]?runs?", re.I), "jobrun"),
    (re.compile(r"add[_\-]?ons?", re.I), "addon"),
    (re.compile(r"change[_\-]?logs?", re.I), "changelog"),
    (re.compile(r"link[_\-]?ed", re.I), "linked"),
    (re.compile(r"star[_\-]?gazers?", re.I), "stargazer"),
    (re.compile(r"issue[_\-]?type", re.I), "issuetype"),
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Shell classification
# --------------------------------------------------------------------------

REDIRECT_RE = re.compile(r"(?<![0-9&<])>{1,2}(?!&)\s*(\S+)?")
SAFE_REDIRECT_TARGETS = {"/dev/null", "&1", "&2"}


def _has_file_redirect(command: str) -> str | None:
    """Return the offending redirect if the command writes to a file."""
    # Ignore quoted strings so `grep ">"` is not a redirect.
    stripped = re.sub(r"'[^']*'|\"[^\"]*\"", "", command)
    for m in REDIRECT_RE.finditer(stripped):
        target = (m.group(1) or "").strip()
        if target in SAFE_REDIRECT_TARGETS:
            continue
        return m.group(0).strip()
    return None


SUBST_RE = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")


def _extract_substitutions(command: str) -> tuple[str, list[str]]:
    """Replace $(...) and `...` with a placeholder; return inner commands."""
    inner: list[str] = []

    def repl(m: re.Match) -> str:
        inner.append(m.group(1) if m.group(1) is not None else m.group(2))
        return "SUBST"

    prev = None
    while prev != command:
        prev = command
        command = SUBST_RE.sub(repl, command)
    return command, inner


def _split_segments(command: str) -> list[list[str]]:
    """Split a shell line into simple commands, each a token list."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    tokens = list(lexer)  # raises ValueError on unbalanced quotes
    segments: list[list[str]] = []
    current: list[str] = []
    for tok in tokens:
        if tok in {"|", "||", "&&", ";", "&", "(", ")", "|&", ";;"}:
            if current:
                segments.append(current)
            current = []
            continue
        current.append(tok)
    if current:
        segments.append(current)
    return [s for s in segments if s]


def _strip_assignments_and_wrappers(seg: list[str]) -> list[str]:
    while seg and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", seg[0]):
        seg = seg[1:]
    while seg and seg[0] in WRAPPER_COMMANDS:
        seg = seg[1:]
        # skip wrapper flags such as `nice -n 10`
        while seg and seg[0].startswith("-"):
            seg = seg[1:]
    return seg


def _positional(args: list[str]) -> list[str]:
    return [a for a in args if not a.startswith("-")]


def _check_git(args: list[str]) -> str | None:
    # skip global options like -C <path>, -c key=val, --no-pager
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] in {"-C", "-c", "--git-dir", "--work-tree"}:
            i += 2
        else:
            i += 1
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]
    if sub in GIT_READONLY:
        return None
    rule = GIT_CONDITIONAL.get(sub)
    if rule is None:
        return f"`git {sub}` changes repository state"
    if rule.get("allow_all"):
        return None
    if "deny_flags" in rule:
        bad = [a for a in rest if a in rule["deny_flags"]]
        if bad:
            return f"`git {sub} {bad[0]}` modifies refs"
        listing_flags = {"-l", "--list", "--contains", "--no-contains",
                         "--points-at", "--merged", "--no-merged", "-a", "-r",
                         "--all", "--remotes", "--show-current"}
        if (not rule.get("allow_positional") and _positional(rest)
                and not set(rest) & listing_flags):
            return f"`git {sub} <name>` creates or modifies a ref; listing only"
        return None
    if "allow_sub" in rule:
        pos = _positional(rest)
        if not pos and sub in {"remote"}:
            return None
        if pos and pos[0] in rule["allow_sub"]:
            return None
        if not pos and set(rest) & rule["allow_sub"]:
            return None
        return f"`git {sub}` is only allowed with {sorted(rule['allow_sub'])}"
    if "require_any" in rule:
        if set(rest) & rule["require_any"]:
            return None
        return f"`git {sub}` is only allowed for reading ({sorted(rule['require_any'])})"
    if "max_positional" in rule:
        if len(_positional(rest)) <= rule["max_positional"]:
            return None
        return f"`git {sub}` with a value would write a ref"
    return f"`git {sub}` is not on the read-only allowlist"


def _check_api_call(cli: str, rest: list[str]) -> str | None:
    for i, a in enumerate(rest):
        if a in API_WRITE_FLAGS:
            if a in {"-X", "--method"} and i + 1 < len(rest) and rest[i + 1].upper() == "GET":
                continue
            return f"`{cli} api {a}` can write; only GET requests are allowed"
        if a.startswith("--method=") and not a.upper().endswith("=GET"):
            return f"`{cli} api {a}` can write; only GET requests are allowed"
    return None


def _check_forge_cli(cli: str, table: dict, args: list[str]) -> str | None:
    pos = _positional(args)
    if not pos:
        return None  # `gh` alone prints help
    noun = pos[0]
    if noun == "api":
        return _check_api_call(cli, args[1:])
    if noun not in table:
        return f"`{cli} {noun}` is not on the read-only allowlist"
    verbs = table[noun]
    if not verbs:
        return None  # e.g. `gh status`
    if len(pos) < 2:
        return f"`{cli} {noun}` needs one of {sorted(verbs)}"
    if pos[1] in verbs:
        # gh pr view --web opens a browser; harmless but not needed.
        return None
    return f"`{cli} {noun} {pos[1]}` is not read-only; allowed verbs: {sorted(verbs)}"


def _check_generic_cli(cli: str, args: list[str]) -> str | None:
    if cli in {"curl", "wget", "http", "https", "httpie", "xh"}:
        bad = [a for a in args if a in WRITE_VERBS_CURL or a.split("=")[0] in WRITE_VERBS_CURL]
        if cli in {"http", "https", "httpie", "xh"}:
            methods = [a for a in _positional(args) if a.upper() in {"POST", "PUT", "PATCH", "DELETE"}]
            bad += methods
        if bad:
            return f"`{cli} {bad[0]}` can send data or write files; GET only"
        return None
    words = {a.lower() for a in _positional(args)[:4]}
    hit = words & WRITE_VERBS
    if hit:
        return f"`{cli}` invoked with write verb `{sorted(hit)[0]}`"
    if words & READ_VERBS:
        return None
    return f"`{cli}` invocation does not look read-only (no read verb such as view/list/get)"


def classify_bash(command: str) -> tuple[str, str]:
    """Return ('deny'|'allow', reason)."""
    if not command.strip():
        return "allow", "empty command"
    redirect = _has_file_redirect(command)
    if redirect:
        return "deny", f"shell redirection `{redirect}` writes to a file; use the Read tool or pipe to head/jq instead"
    outer, inner_commands = _extract_substitutions(command)
    try:
        segments = _split_segments(outer)
        for inner in inner_commands:
            segments.extend(_split_segments(inner))
    except ValueError as e:
        return "deny", f"could not parse command safely ({e})"
    for seg in segments:
        seg = _strip_assignments_and_wrappers(seg)
        if not seg:
            continue
        cmd, args = os.path.basename(seg[0]), seg[1:]
        if cmd in DENIED_COMMANDS:
            return "deny", f"`{cmd}` can change state; reviewers only inspect"
        if cmd == "git":
            why = _check_git(args)
        elif cmd == "gh":
            why = _check_forge_cli("gh", GH_READONLY, args)
        elif cmd == "glab":
            why = _check_forge_cli("glab", GLAB_READONLY, args)
        elif cmd in GENERIC_CLIS:
            why = _check_generic_cli(cmd, args)
        elif cmd in READONLY_COMMANDS:
            why = _check_readonly_utility(cmd, args)
        elif cmd == "cd":
            why = None
        else:
            why = f"`{cmd}` is not on the read-only allowlist"
        if why:
            return "deny", why
    return "allow", "read-only command"


def _check_readonly_utility(cmd: str, args: list[str]) -> str | None:
    if cmd == "sed" and any(a == "-i" or a.startswith("-i") or a == "--in-place" or a.startswith("--in-place") for a in args):
        return "`sed -i` edits files in place"
    if cmd == "find" and any(a in {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprintf", "-fls"} for a in args):
        return "`find` with -delete/-exec can change state"
    if cmd == "awk" and any(">" in a or "system(" in a for a in args):
        return "`awk` program writes files or runs commands"
    return None


# --------------------------------------------------------------------------
# MCP classification
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def decide(payload: dict) -> dict | None:
    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}

    scope = _globs("READONLY_GUARD_AGENTS")
    if scope:
        agent = (payload.get("agent_type") or payload.get("agent_name")
                 or payload.get("subagent_type") or "")
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


def main() -> int:
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
