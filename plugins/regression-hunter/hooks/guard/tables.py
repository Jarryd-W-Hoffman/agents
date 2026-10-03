"""Lookup tables: which tools, commands and MCP names are reads.

Part of the read-only guard. The entry point is `hooks/readonly-guard.py`;
this module is not meant to be run directly.
"""

from __future__ import annotations

import re

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
    "type", "whoami", "id", "date", "printenv", "basename",
    "dirname", "realpath", "readlink", "md5sum", "shasum", "sha256sum",
    "strings", "column", "paste", "nl", "tac", "rev", "seq", "sleep",
    "hostname", "uname", "xxd", "hexdump", "od", "expr", "bc", "tput",
    "man", "help", "sed",
}

# Wrappers that run another command; unwrap and inspect the inner command.
# `env` is a wrapper too: a bare `env` prints the environment, but
# `env rm x` runs rm, so its own options are stripped in _unwrap_env.
WRAPPER_COMMANDS = {"time", "command", "nice", "ionice", "caffeinate", "env"}
# Wrapper options that take a value (`nice -n 10`, `ionice -c 3`, `caffeinate -t 60`).
WRAPPER_VALUE_FLAGS = {
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "--class", "-n", "--classdata", "-p", "--pid"},
    "caffeinate": {"-t", "-w"},
    "time": {"-f", "--format"},
}
# GNU `time -o FILE` writes the timing to a file.
WRAPPER_DENIED_FLAGS = {"-o", "--output", "-a", "--append"}

# Environment variables that change what a "read-only" command executes
# (external diff drivers, editors, pagers, loader hooks, interpreter start-up
# files). A `NAME=value` prefix or `env NAME=value` naming one is denied.
DANGEROUS_ENV_VARS = re.compile(
    r"^(PATH|LD_PRELOAD|LD_LIBRARY_PATH|DYLD_.*|GIT_EXTERNAL_DIFF|GIT_DIFF_OPTS"
    r"|GIT_EDITOR|GIT_SEQUENCE_EDITOR|EDITOR|VISUAL|GIT_SSH|GIT_SSH_COMMAND"
    r"|GIT_ASKPASS|SSH_ASKPASS|GIT_EXEC_PATH|GIT_PROXY_COMMAND|GIT_CONFIG.*"
    r"|GIT_TRACE.*|GIT_DIR|GIT_WORK_TREE|GIT_INDEX_FILE|GIT_OBJECT_DIRECTORY"
    r"|GIT_ALTERNATE_OBJECT_DIRECTORIES|GIT_TEMPLATE_DIR|BASH_ENV|ENV"
    r"|PROMPT_COMMAND|LESSOPEN|LESSCLOSE|PYTHONSTARTUP|NODE_OPTIONS|PERL5OPT"
    r"|RUBYOPT)$"
)
# Pager variables are fine when they disable paging; anything else runs a command.
PAGER_ENV_VARS = {"PAGER", "GIT_PAGER", "GH_PAGER", "GLAB_PAGER"}
SAFE_PAGER_VALUES = {"", "cat"}

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
    "wget",  # writes to disk by default; use `curl -s` or WebFetch
}

# Denied commands that are still a pure read when their ONLY argument asks for
# a version. A compliance pass checking "policy says Node 20+" should not have
# to give up. The match is exact and single-argument: `python3 --version` is
# allowed, `python3 --version -c ...` is not, so there is no way to smuggle a
# script past it. `-v` is deliberately absent -- for python it means verbose,
# and starts a REPL.
VERSION_ONLY_ARGS = {"--version", "-V"}
# Some of the same tools spell it as a subcommand: `go version`, `docker
# version`. Same rule -- it has to be the only argument.
VERSION_ONLY_SUBCOMMANDS = {"version"}
VERSION_READABLE = {
    "python", "python3", "node", "ruby", "perl", "php", "deno", "bun",
    "npm", "pnpm", "yarn", "go", "cargo", "make", "docker", "kubectl",
    "terraform", "composer", "pip", "pip3", "mvn", "gradle",
}

# git subcommands that never change the working tree, index, refs or config.
GIT_READONLY = {
    "status", "log", "diff", "show", "blame", "rev-parse", "rev-list",
    "ls-files", "ls-tree", "ls-remote", "cat-file", "grep", "shortlog",
    "describe", "merge-base", "name-rev", "for-each-ref", "count-objects",
    "check-ignore", "check-attr", "diff-tree", "diff-index", "diff-files",
    "whatchanged", "var", "version", "help", "range-diff",
    "cherry", "show-ref", "show-branch", "verify-commit", "verify-tag",
}
# Global options (before the subcommand) that make git run something else.
GIT_DENIED_GLOBAL_OPTIONS = {"-c", "--config-env", "--exec-path"}
# Options every git subcommand accepts that write a file or run a command.
# `--ext-diff` runs `diff.external` and `--textconv` runs a `diff.*.textconv`
# filter, both of which are commands taken from configuration -- the same
# hazard as GIT_EXTERNAL_DIFF and `git -c diff.external=`, which are already
# denied. The `--no-` spellings turn the behaviour off and stay allowed.
GIT_DENIED_ANY_OPTIONS = {"--output", "--ext-diff", "--textconv"}
# git subcommands that are read-only only with these argument shapes.
# `deny_flags` are compared on the option name only (`--flag=value` and
# bundled short flags such as `-fd` are normalised first).
GIT_CONDITIONAL = {
    # branch: listing only (no positional args that would create/delete)
    "branch": {"deny_flags": {"-d", "-D", "-m", "-M", "-c", "-C", "--delete",
                              "--move", "--copy", "--set-upstream-to", "-u",
                              "--unset-upstream", "--edit-description", "-f",
                              "--force", "-t", "--track"},
               "allow_positional": False},
    "tag": {"deny_flags": {"-a", "-d", "-f", "-s", "-m", "-F", "--delete",
                           "--annotate", "--sign", "--force"},
            "allow_positional": False},
    "remote": {"allow_sub": {"-v", "--verbose", "show", "get-url"}},
    "stash": {"allow_sub": {"list", "show"}},
    "worktree": {"allow_sub": {"list"}},
    "notes": {"allow_sub": {"show", "list"}},
    # reflog: bare `git reflog` and `git reflog show`; expire/delete drop refs.
    "reflog": {"allow_sub": {"show"}, "allow_bare": True},
    "config": {"require_any": {"--get", "--get-all", "--get-regexp", "--list",
                               "-l", "--show-origin", "--show-scope"},
               "deny_flags": {"--unset", "--unset-all", "--add",
                              "--replace-all", "--remove-section",
                              "--rename-section", "-e", "--edit"}},
    "symbolic-ref": {"max_positional": 1,
                     "deny_flags": {"-d", "--delete", "-m"}},
    # fetch updates remote-tracking refs only, which reviewers need for PR
    # branches. A refspec (`src:dst`) or any option that rewrites local refs,
    # tags or history depth is denied.
    "fetch": {"deny_flags": {"-f", "--force", "--update-head-ok", "-p",
                             "--prune", "-P", "--prune-tags", "-t", "--tags",
                             "--refmap", "--set-upstream", "--unshallow",
                             "--deepen", "--deepen-since", "--deepen-not",
                             "--depth"},
              "deny_positional_re": r":"},
    "fsck": {"deny_flags": {"--lost-found"}},
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
# `gh api` / `glab api`: the method flags are allowed only with GET/HEAD; the
# body flags always send data. `gh api graphql -f query=...` is therefore
# denied too: a field cannot be told apart from a mutation. That is intended.
API_METHOD_FLAGS = {"-X", "--method"}
API_BODY_FLAGS = {"-f", "-F", "--field", "--raw-field", "--input"}
API_READ_METHODS = {"GET", "HEAD"}

# Generic CLIs (issue trackers, clouds, etc.): allowed when a read verb is
# present and no write verb appears anywhere in the arguments.
GENERIC_CLIS = {
    "jira", "acli", "linear", "lin", "linear-cli", "confluence", "sentry-cli",
    "aws", "az", "gcloud", "doctl", "vercel", "netlify", "heroku", "fly",
    "flyctl", "railway", "stripe", "slack", "trello", "asana", "notion",
    "clickup", "shortcut", "monday", "gh-dash", "tea", "bb", "hub",
}
# HTTP clients get their own option tables (see _check_http_cli).
CURL_CLIS = {"curl"}
HTTPIE_CLIS = {"http", "https", "httpie", "xh"}
READ_VERBS = {
    "view", "list", "ls", "get", "show", "diff", "status", "checks", "search",
    "log", "logs", "cat", "print", "describe", "read", "info", "me", "whoami",
    "version", "help", "query", "find", "fetch", "lookup", "count", "check",
    "history", "browse", "tail", "head", "watch", "trace", "explain",
    "validate", "lint", "test", "dry-run", "preview", "inspect", "retrieve",
}
WRITE_VERBS = {
    "download", "export",  # exist to write files
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
# curl is allow-listed (fail closed): only these options may appear, and only
# GET/HEAD reads to stdout are allowed. Everything else (-d, --json, -F, -T,
# -o, -O, -c, -D, --trace*, -K, ...) is denied.
CURL_ALLOWED_FLAGS = {
    "-s", "-S", "--silent", "--show-error", "-L", "--location", "-f", "--fail",
    "--fail-with-body", "-I", "--head", "-G", "--get", "--compressed", "-k",
    "--insecure", "-v", "--verbose", "-4", "-6", "--http1.1", "--http2",
    "--no-progress-meter", "--globoff", "-g", "-N", "--no-buffer", "-#",
    "--progress-bar", "--tlsv1.2", "--tlsv1.3", "-i", "--include",
    "--http1.0", "--http3", "--ipv4", "--ipv6", "--path-as-is",
}
# Options that take a value (the next token, or `--opt=value` / `-Hvalue`).
CURL_ALLOWED_FLAGS_WITH_VALUE = {
    "-H", "--header", "-A", "--user-agent", "-b", "--cookie", "-m",
    "--max-time", "--connect-timeout", "--retry", "--retry-delay", "-w",
    "--write-out", "--url", "-u", "--user", "-x", "--proxy", "-e", "--referer",
    "--max-redirs", "--cacert", "--capath", "--cert", "--key",
}
CURL_METHOD_FLAGS = {"-X", "--request"}
# `-w` is a read (it prints transfer info), except that curl >= 8.3 writes to a
# file when the format string contains `%output{name}` (or `%output{>>name}`).
CURL_WRITE_OUT_FLAGS = {"-w", "--write-out"}
CURL_WRITE_OUT_TO_FILE = "%output{"

# HTTPie / xh: options that write files, send bodies or persist sessions.
HTTPIE_DENIED_FLAGS = {"-d", "--download", "-o", "--output", "-f", "--form",
                       "-j", "--json", "--raw", "--session",
                       "--session-read-only"}
# Request items that send a body: `k=v`, `k:=json`, `k@file`. `k==v` is a
# query parameter and `k:v` a header, both reads.
HTTPIE_BODY_ITEM_RE = re.compile(r"^[^=:@]+(=(?!=)|:=|@)")
# HTTPie and xh default to POST whenever stdin has data, and the hook's stdin
# is never a TTY, so a read is only guaranteed when stdin is explicitly ignored.
HTTPIE_IGNORE_STDIN_FLAGS = {"--ignore-stdin", "-I"}
# HTTPie treats a leading all-alphabetic positional as the method.
HTTPIE_METHOD_RE = re.compile(r"^[A-Za-z]+$")

# --------------------------------------------------------------------------
# MCP tools
# --------------------------------------------------------------------------

# Verbs that unambiguously change state when they appear anywhere in a tool name.
MCP_STRONG_WRITE = {
    "download", "downloads", "export", "exports",  # write files
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
    "check", "browse", "inspect", "preview", "diff",
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
