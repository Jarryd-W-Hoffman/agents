"""Shell command classification: is this command a read?

Part of the read-only guard. The entry point is `hooks/readonly-guard.py`;
this module is not meant to be run directly.
"""

from __future__ import annotations

import os
import re
import shlex

# tables.py is constants only, so a star import keeps the ~40 names readable
# at their use sites instead of prefixing every one of them.
from .tables import *  # noqa: F401,F403
# Every output redirect form: `>`, `>>`, `&>`, `&>>`, `N>`, `N>>`, `>&`.
# `<` / `<<` / `<<<` are input redirects and never match; the `(?<!<)`
# guard keeps the `>` of a `<>` read-write open from matching on its own.
REDIRECT_RE = re.compile(r"(?<!<)(?:\d*|&)>{1,2}(&?)\s*([^\s|&;()]*)")
# A backslash-escaped quote is a literal character, not a delimiter, so
# `echo \\"a > out \\"b` really does redirect. Skip escaped quotes when pairing,
# and allow escapes inside a double-quoted string.
QUOTED_RE = re.compile(r"(?<!\\)'[^']*'|(?<!\\)\"(?:[^\"\\]|\\.)*\"")


def _strip_quotes(command: str) -> str:
    """Remove quoted strings so `grep ">"` is not a redirect."""
    return QUOTED_RE.sub("", command)


def _has_file_redirect(command: str) -> str | None:
    """Return the offending redirect if the command writes to a file.

    Only two output redirects are allowed: to /dev/null (with or without a
    file descriptor prefix) and file-descriptor duplication (`2>&1`).
    """
    for m in REDIRECT_RE.finditer(_strip_quotes(command)):
        dup, target = m.group(1), m.group(2)
        if dup == "&" and re.fullmatch(r"\d+", target):
            continue  # `2>&1`, `>&2`
        if not dup and target == "/dev/null":
            continue  # `2>/dev/null`, `&>/dev/null`
        return m.group(0).strip()
    return None


# The two output redirects the guard allows, removed before lexing so their
# tokens (`2`, `>`, `/dev/null`) are not mistaken for positional arguments.
SAFE_REDIRECT_RE = re.compile(r"(?:\d*|&)>{1,2}(?:&\d+|\s*/dev/null)")


def _strip_safe_redirects(line: str) -> str:
    """Remove `N>/dev/null` and `N>&M`; only call after _has_file_redirect passed."""
    return SAFE_REDIRECT_RE.sub(" ", line)


PROCESS_SUBST_RE = re.compile(r"[<>]\(")


def _has_process_substitution(command: str) -> bool:
    """True if the command uses `<(...)` or `>(...)`, which hide a command."""
    return bool(PROCESS_SUBST_RE.search(_strip_quotes(command)))


def _split_lines(command: str) -> list[str]:
    """Split on unquoted newlines; a newline inside quotes is not a separator.

    shlex treats newlines as whitespace, so without this `git status\\nrm x`
    would lex as a single `git status` segment.
    """
    lines: list[str] = []
    current: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(command):
        ch = command[i]
        if quote is None and ch == "\\" and i + 1 < len(command):
            # `\` + newline is a line continuation: join with a space.
            current.append(" " if command[i + 1] == "\n" else command[i:i + 2])
            i += 2
            continue
        if quote == '"' and ch == "\\" and i + 1 < len(command):
            current.append(command[i:i + 2])
            i += 2
            continue
        if quote is None and ch in "'\"":
            quote = ch
        elif quote == ch:
            quote = None
        elif quote is None and ch == "\n":
            lines.append("".join(current))
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    lines.append("".join(current))
    return [line for line in lines if line.strip()]


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


ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)


def _normalise_flags(args: list[str], with_value: set[str] = frozenset()) -> list[str]:
    """Expand attached option spellings so checks see one form.

    `--long=value` becomes `--long`, `value`. A bundled short group such as
    `-sSLO` becomes `-s`, `-S`, `-L`, `-O`. When a short option in
    `with_value` is met, the rest of the token is its value: `-XPOST`
    becomes `-X`, `POST` and `-fbody=hi` becomes `-f`, `body=hi`.
    """
    out: list[str] = []
    for a in args:
        if a.startswith("--"):
            out.extend(a.split("=", 1))
        elif re.fullmatch(r"-[A-Za-z].+", a, re.S):
            for j, ch in enumerate(a[1:], start=1):
                out.append("-" + ch)
                if "-" + ch in with_value:
                    if j + 1 < len(a):
                        out.append(a[j + 1:])
                    break
        else:
            out.append(a)
    return out


def _values_of(args: list[str], names: set[str]) -> list[str]:
    """Values following any option in `names` (call on normalised args)."""
    return [args[i + 1] for i, a in enumerate(args)
            if a in names and i + 1 < len(args)]


def _dangerous_assignment(name: str, value: str) -> str | None:
    """Reason if `NAME=value` would change what a read-only command runs."""
    if DANGEROUS_ENV_VARS.match(name):
        return f"setting `{name}` can make a read-only command run something else"
    if name in PAGER_ENV_VARS and value not in SAFE_PAGER_VALUES:
        return f"`{name}={value}` runs a pager command; use `{name}=cat`"
    return None


def _unwrap_env(seg: list[str]) -> tuple[list[str], str | None]:
    """Strip `env`'s own options and assignments; return (rest, reason)."""
    i = 0
    while i < len(seg):
        a = seg[i]
        m = ASSIGNMENT_RE.match(a)
        if m:
            why = _dangerous_assignment(m.group(1), m.group(2))
            if why:
                return seg, why
            i += 1
        elif a in {"-S", "--split-string"} or a.startswith(("-S", "--split-string=")):
            return seg, "`env -S` re-parses a string as a command; run it directly"
        elif a in {"-i", "--ignore-environment", "-", "-0", "--null"}:
            i += 1
        elif a in {"-u", "--unset", "-C", "--chdir"}:
            i += 2
        elif a.startswith(("--unset=", "--chdir=", "-u", "-C")):
            i += 1
        elif a.startswith("-"):
            return seg, f"`env {a}` is not a recognised read-only option"
        else:
            break
    return seg[i:], None


def _strip_assignments_and_wrappers(seg: list[str]) -> tuple[list[str], str | None]:
    """Drop `NAME=value` prefixes and wrapper commands; return (rest, reason).

    A dangerous assignment (see DANGEROUS_ENV_VARS) returns a deny reason
    instead of being silently dropped.
    """
    while seg and (m := ASSIGNMENT_RE.match(seg[0])):
        why = _dangerous_assignment(m.group(1), m.group(2))
        if why:
            return seg, why
        seg = seg[1:]
    while seg and os.path.basename(seg[0]) in WRAPPER_COMMANDS:
        wrapper, seg = os.path.basename(seg[0]), seg[1:]
        if wrapper == "env":
            seg, why = _unwrap_env(seg)
            if why:
                return seg, why
            continue
        # skip wrapper flags such as `nice -n 10`
        while seg and seg[0].startswith("-"):
            flag = seg[0].split("=", 1)[0]
            if flag in WRAPPER_DENIED_FLAGS:
                return seg, f"`{wrapper} {flag}` writes a file"
            takes_value = flag in WRAPPER_VALUE_FLAGS.get(wrapper, set()) and "=" not in seg[0]
            seg = seg[2:] if takes_value else seg[1:]
    return seg, None


def _positional(args: list[str]) -> list[str]:
    return [a for a in args if not a.startswith("-")]


def _split_git_global_options(args: list[str]) -> tuple[str | None, str | None, list[str]]:
    """Return (reason, subcommand, rest) after the global options.

    Skips `-C <path>`, `--git-dir=<x>`, `--no-pager` and friends; denies the
    options that make git run something else (`-c diff.external=rm`).
    """
    i = 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        # `-cKEY=VAL` attaches its value, so match the prefix as well as the name.
        if a.split("=", 1)[0] in GIT_DENIED_GLOBAL_OPTIONS or a.startswith("-c"):
            return f"git global option `{a}` can change what git runs", None, []
        if a in {"-C", "--git-dir", "--work-tree", "--namespace"}:
            i += 2
        else:
            i += 1
    if i >= len(args):
        return None, None, []
    return None, args[i], args[i + 1:]


def _git_denied_flag(flags: list[str], denied: set[str]) -> str | None:
    """The first flag that is, or abbreviates, an option in `denied`.

    git takes any unambiguous prefix of a long option, so `--upload-p` is
    `--upload-pack`. A bare `--` ends the options and is never a match.
    """
    for a in flags:
        if a in denied:
            return a
        if (a.startswith("--") and len(a) > 3
                and a not in GIT_PREFIX_EXEMPT_OPTIONS
                and any(d.startswith(a) for d in denied)):
            return a
    return None


def _check_git(args: list[str]) -> str | None:
    why, sub, rest = _split_git_global_options(args)
    if why:
        return why
    if sub is None:
        return None
    flags = _normalise_flags(rest)
    bad = _git_denied_flag(flags, GIT_DENIED_ANY_OPTIONS)
    if bad:
        return f"`git {sub} {bad}` writes a file or runs a command; read the output instead"
    bad = _git_denied_flag(flags, GIT_DENIED_SUBCOMMAND_OPTIONS.get(sub, set()))
    if bad:
        return f"`git {sub} {bad}` runs a command; use `git {sub}` without it"
    if sub in GIT_READONLY:
        return None
    rule = GIT_CONDITIONAL.get(sub)
    if rule is None:
        return f"`git {sub}` changes repository state"
    pos = _positional(rest)
    if "deny_flags" in rule:
        bad = _git_denied_flag(flags, rule["deny_flags"])
        if bad:
            return f"`git {sub} {bad}` modifies refs"
    if "deny_positional_re" in rule:
        bad = [p for p in pos if re.search(rule["deny_positional_re"], p)]
        if bad:
            return f"`git {sub} {bad[0]}` is a refspec that writes a local ref"
    if "allow_sub" in rule:
        if not pos and (sub == "remote" or rule.get("allow_bare")):
            return None
        if pos and pos[0] in rule["allow_sub"]:
            return None
        if not pos and set(rest) & rule["allow_sub"]:
            return None
        return f"`git {sub}` is only allowed with {sorted(rule['allow_sub'])}"
    if "require_any" in rule:
        if set(flags) & rule["require_any"]:
            return None
        return f"`git {sub}` is only allowed for reading ({sorted(rule['require_any'])})"
    if "max_positional" in rule:
        if len(pos) <= rule["max_positional"]:
            return None
        return f"`git {sub}` with a value would write a ref"
    if "allow_positional" in rule:
        listing_flags = {"-l", "--list", "--contains", "--no-contains",
                         "--points-at", "--merged", "--no-merged", "-a", "-r",
                         "--all", "--remotes", "--show-current"}
        if (not rule["allow_positional"] and pos
                and not set(flags) & listing_flags):
            return f"`git {sub} <name>` creates or modifies a ref; listing only"
        return None
    if "deny_flags" in rule or "deny_positional_re" in rule:
        return None  # only the deny checks above apply (fetch, fsck)
    return f"`git {sub}` is not on the read-only allowlist"


def _check_api_call(cli: str, rest: list[str]) -> str | None:
    """`gh api` / `glab api`: GET/HEAD without a body, in any flag spelling."""
    flags = _normalise_flags(rest, with_value=API_METHOD_FLAGS | API_BODY_FLAGS)
    bad = [a for a in flags if a in API_BODY_FLAGS]
    if bad:
        return f"`{cli} api {bad[0]}` sends a request body; only GET/HEAD reads are allowed"
    methods = [m.upper() for m in _values_of(flags, API_METHOD_FLAGS)]
    bad = [m for m in methods if m not in API_READ_METHODS]
    if bad:
        return f"`{cli} api` with method {bad[0]} can write; only GET/HEAD are allowed"
    return None


def _check_forge_cli(cli: str, table: dict, args: list[str]) -> str | None:
    pos = _positional(args)
    if not pos:
        return None  # `gh` alone prints help
    noun = pos[0]
    if noun == "api":
        return _check_api_call(cli, args[args.index("api") + 1:])
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


def _check_curl(args: list[str]) -> str | None:
    """curl: only allow-listed options, GET/HEAD, output to stdout."""
    flags = _normalise_flags(args, with_value=CURL_ALLOWED_FLAGS_WITH_VALUE | CURL_METHOD_FLAGS)
    i = 0
    while i < len(flags):
        a = flags[i]
        if a in CURL_ALLOWED_FLAGS or not a.startswith("-") or a == "-":
            i += 1
        elif a in CURL_ALLOWED_FLAGS_WITH_VALUE:
            value = flags[i + 1] if i + 1 < len(flags) else ""
            if a in CURL_WRITE_OUT_FLAGS and CURL_WRITE_OUT_TO_FILE in value:
                return f"`curl {a}` with `%output{{}}` writes a file; only GET/HEAD reads to stdout are allowed (prefer WebFetch)"
            i += 2
        elif a in CURL_METHOD_FLAGS:
            method = flags[i + 1].upper() if i + 1 < len(flags) else ""
            if method not in API_READ_METHODS:
                return f"`curl {a} {method}` can write; only GET/HEAD reads to stdout are allowed (prefer WebFetch)"
            i += 2
        else:
            return f"`curl {a}` is not allowed; only GET/HEAD reads to stdout are allowed (prefer WebFetch)"
    return None


def _check_httpie(cli: str, args: list[str]) -> str | None:
    """HTTPie / xh: GET/HEAD, stdin ignored, no body items, no downloads."""
    flags = _normalise_flags(args)
    bad = [a for a in flags if a in HTTPIE_DENIED_FLAGS]
    if bad:
        return f"`{cli} {bad[0]}` sends data or writes files; only GET/HEAD reads are allowed (prefer WebFetch)"
    if not set(flags) & HTTPIE_IGNORE_STDIN_FLAGS:
        return (f"`{cli}` sends anything on stdin as a POST body; pass `--ignore-stdin` "
                "for a GET (or prefer WebFetch)")
    for i, p in enumerate(_positional(args)):
        if i == 0 and HTTPIE_METHOD_RE.match(p):
            if p.upper() not in API_READ_METHODS:
                return f"`{cli} {p}` can write; only GET/HEAD reads are allowed (prefer WebFetch)"
            continue
        if HTTPIE_BODY_ITEM_RE.match(p) and "://" not in p:
            return f"`{cli} {p}` is a request body item; only GET/HEAD reads are allowed (prefer WebFetch)"
    return None


def _check_http_cli(cli: str, args: list[str]) -> str | None:
    if cli in CURL_CLIS:
        return _check_curl(args)
    return _check_httpie(cli, args)


def _check_generic_cli(cli: str, args: list[str]) -> str | None:
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
    if _has_process_substitution(command):
        return "deny", "process substitution `<(...)`/`>(...)` hides a command; run the inner command separately"
    try:
        segments: list[list[str]] = []
        for line in _split_lines(command):
            outer, inner_commands = _extract_substitutions(_strip_safe_redirects(line))
            segments.extend(_split_segments(outer))
            for inner in inner_commands:
                segments.extend(_split_segments(inner))
    except ValueError as e:
        return "deny", f"could not parse command safely ({e})"
    for seg in segments:
        seg, why = _strip_assignments_and_wrappers(seg)
        if why:
            return "deny", why
        if not seg:
            continue
        # A residual `<(` token here can only come from a quoted string
        # (`grep '<('`): unquoted forms were denied on the raw command above.
        cmd, args = os.path.basename(seg[0]), seg[1:]
        if cmd in DENIED_COMMANDS:
            if cmd in VERSION_READABLE and len(args) == 1 and (
                    args[0] in VERSION_ONLY_ARGS
                    or args[0] in VERSION_ONLY_SUBCOMMANDS):
                continue  # `python3 --version` / `go version`, and nothing else
            return "deny", f"`{cmd}` can change state; reviewers only inspect"
        if cmd == "git":
            why = _check_git(args)
        elif cmd == "gh":
            why = _check_forge_cli("gh", GH_READONLY, args)
        elif cmd == "glab":
            why = _check_forge_cli("glab", GLAB_READONLY, args)
        elif cmd in CURL_CLIS or cmd in HTTPIE_CLIS:
            why = _check_http_cli(cmd, args)
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


# Allow-listed utilities with an option that writes a file or runs a command.
# Options are matched on normalised flags, so `-oFILE`, `--output=FILE` and
# bundled `-Ei` are caught too.
UTILITY_DENIED_FLAGS: dict[str, tuple[set[str], str]] = {
    # `-I` is BSD/macOS in-place editing, the same write as `-i`.
    "sed": ({"-i", "-I", "--in-place", "-f", "--file"},
            "`sed -i` edits files in place and `-f` runs an unknown script file"),
    # gawk: -p/-o/-d write profile and variable dumps, -E/-f run an unknown
    # program file, -l/-i load an extension or library.
    "awk": ({"-f", "--file", "-E", "--exec", "-p", "--profile", "-o",
             "--pretty-print", "-d", "--dump-variables", "-l", "--load",
             "-i", "--include"},
            "`awk -f`/`-E` runs an unknown program file and `-p`/`-o`/`-d` write one"),
    "sort": ({"-o", "--output"}, "`sort -o` writes a file; pipe to head instead"),
    "yq": ({"-i", "--inplace"}, "`yq -i` edits files in place"),
    "tree": ({"-o", "--output"}, "`tree -o` writes a file"),
    "less": ({"-o", "-O", "--log-file", "--LOG-FILE"}, "`less -o` logs to a file"),
    "fd": ({"-x", "--exec", "-X", "--exec-batch"}, "`fd --exec` runs a command per result"),
    "rg": ({"--pre", "--pre-glob"}, "`rg --pre` runs a preprocessor command"),
    "date": ({"-s", "--set"}, "`date -s` sets the system clock"),
    "find": ({"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint",
              "-fprint0", "-fprintf", "-fls"},
             "`find` with -delete/-exec/-fprint can change state"),
}
# Options that take a value, per command. Without these an attached value is
# bundle-expanded into letters that collide with other options (`date
# -Iseconds` would read as `-I -s ...` and look like `date -s`), and a
# space-separated value is mistaken for the script or program.
UTILITY_VALUE_FLAGS: dict[str, set[str]] = {
    "sed": {"-e", "--expression", "-i", "-I", "--in-place", "-l",
            "--line-length", "-f", "--file"},
    "awk": {"-F", "--field-separator", "-v", "--assign", "-e", "--source",
            "-f", "--file", "-E", "--exec", "-l", "--load", "-i", "--include"},
    "date": {"-d", "--date", "-r", "--reference", "-f", "--file", "-s",
             "--set", "-I", "--iso-8601"},
}
# sed writes with the `w`/`W` commands, the `w` flag of `s`, and runs commands
# with `e` (command or `s` flag). Those only count in command position, so the
# script is scanned command by command rather than pattern-matched: `s/e/x/`
# and `/error/p` are reads, `s/a/b/w out` and `1w out` are writes.
SED_TEXT_COMMANDS = set("aic")          # text to end of line (GNU one-liner form)
SED_FILE_COMMANDS = set("rR")           # read a file: filename to end of line
SED_LABEL_COMMANDS = set("btT:")        # label to `;` or end of line
SED_SIMPLE_COMMANDS = set("pPdDnNhHgGxlzF=qQv")


def _sed_skip_delimited(script: str, i: int, delim: str) -> int | None:
    """Index just past the closing `delim`, honouring backslash escapes."""
    while i < len(script):
        if script[i] == "\\":
            i += 2
        elif script[i] == delim:
            return i + 1
        else:
            i += 1
    return None


def _sed_skip_address(script: str, i: int) -> int | None:
    """Skip an address range (`1`, `$`, `/re/I`, `\\,re,`, `a,b`, `0~3`, `!`)."""
    n = len(script)
    while i < n:
        c = script[i]
        if c.isdigit() or c in "$,~+! \t":
            i += 1
        elif c == "/" or (c == "\\" and i + 1 < n):
            delim = "/" if c == "/" else script[i + 1]
            end = _sed_skip_delimited(script, i + (1 if c == "/" else 2), delim)
            if end is None:
                return None
            i = end
            while i < n and script[i] in "IM":  # regex modifiers
                i += 1
        else:
            break
    return i


def _sed_script_writes(script: str) -> bool:
    """True if the script writes a file or runs a command, or cannot be parsed."""
    n = len(script)
    i = 0
    while i < n:
        if script[i] in " \t\n;}":
            i += 1
            continue
        i = _sed_skip_address(script, i)
        if i is None:
            return True
        if i >= n:
            break
        c = script[i]
        if c in "wWe":
            return True
        if c == "{":
            i += 1
        elif c == "#":
            i = script.find("\n", i)
            i = n if i < 0 else i
        elif c in "sy":
            if i + 1 >= n:
                return True
            delim = script[i + 1]
            end = _sed_skip_delimited(script, i + 2, delim)
            end = _sed_skip_delimited(script, end, delim) if end is not None else None
            if end is None:
                return True
            i = end
            if c == "s":  # flags: g, p, i, I, m, M, digits; w FILE and e are writes
                while i < n and script[i] not in ";\n}":
                    if script[i] in "we":
                        return True
                    i += 1
        elif c in SED_TEXT_COMMANDS or c in SED_FILE_COMMANDS:
            i = script.find("\n", i)
            i = n if i < 0 else i
        elif c in SED_LABEL_COMMANDS:
            i += 1
            while i < n and script[i] not in ";\n":
                i += 1
        elif c in SED_SIMPLE_COMMANDS:
            i += 1
            while i < n and (script[i].isdigit() or script[i] in " \t"):
                i += 1
            if i < n and script[i] not in ";\n}":
                return True  # trailing junk: not a shape we understand
        else:
            return True  # unknown command: fail closed
    return False


# awk writes with `>`/`>>` in a print/printf statement, and runs commands with
# `|` (`print | "sh"`, `"cmd" | getline`) or system(). `||` is logical-or and
# `>` outside print (`NR > 5`) is a comparison; strings and regex literals
# are skipped so `print "a > b"` and `/a|b/` are not mistaken for writes.
AWK_REGEX_START_CHARS = set("(,{;!~&|=<>?:")
AWK_REGEX_START_WORDS = {"if", "while", "print", "printf", "return", "in", "do", "else"}


def _awk_program_writes(program: str) -> bool:
    n = len(program)
    i = 0
    depth = 0
    in_print = False
    prev = ""            # previous significant character
    prev_word = ""       # previous identifier
    while i < n:
        c = program[i]
        if c == '"':
            i += 1
            while i < n and program[i] != '"':
                i += 2 if program[i] == "\\" else 1
            i += 1
            prev, prev_word = '"', ""
            continue
        if c == "/" and (prev == "" or prev in AWK_REGEX_START_CHARS
                         or prev_word in AWK_REGEX_START_WORDS):
            i += 1
            while i < n and program[i] != "/":
                i += 2 if program[i] == "\\" else 1
            i += 1
            prev, prev_word = "/", ""
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (program[j].isalnum() or program[j] == "_"):
                j += 1
            word = program[i:j]
            if word == "system":
                return True
            if word in {"print", "printf"} and depth == 0:
                in_print = True
            prev, prev_word = word[-1], word
            i = j
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth = max(0, depth - 1)
        elif c == "|":
            if i + 1 < n and program[i + 1] == "|":
                i += 2
                prev, prev_word = "|", ""
                continue
            return True
        elif c in ";\n{}":
            in_print = False
        elif c == ">" and in_print and depth == 0:
            return True
        if not c.isspace():
            prev, prev_word = c, ""
        i += 1
    return False


def _sed_scripts(args: list[str]) -> list[str]:
    """The sed script(s): every -e/--expression value, else the first positional."""
    value_options = UTILITY_VALUE_FLAGS["sed"]
    flags = _normalise_flags(args, with_value=value_options)
    scripts = _values_of(flags, {"-e", "--expression"})
    if scripts:
        return scripts
    first = _first_positional(flags, value_options)
    return [first] if first else []


def _check_sed(args: list[str]) -> str | None:
    for script in _sed_scripts(args):
        if _sed_script_writes(script):
            return "`sed` script writes a file (`w`) or runs a command (`e`)"
    return None


def _awk_programs(args: list[str]) -> list[str]:
    """The awk program(s): every -e/--source value, else the first positional."""
    value_options = UTILITY_VALUE_FLAGS["awk"]
    flags = _normalise_flags(args, with_value=value_options)
    programs = _values_of(flags, {"-e", "--source"})
    if programs:
        return programs
    first = _first_positional(flags, value_options)
    return [first] if first else []


def _first_positional(flags: list[str], with_value: set[str]) -> str | None:
    """First non-option token, skipping the values of options in `with_value`."""
    i = 0
    while i < len(flags):
        if flags[i] in with_value:
            i += 2
        elif flags[i].startswith("-"):
            i += 1
        else:
            return flags[i]
    return None


def _check_awk(args: list[str]) -> str | None:
    for program in _awk_programs(args):
        if _awk_program_writes(program):
            return "`awk` program writes files or runs commands"
    return None


def _check_uniq(args: list[str]) -> str | None:
    if len(_positional(args)) >= 2:
        return "`uniq IN OUT` writes a file; pipe the output instead"
    return None


def _check_hostname(args: list[str]) -> str | None:
    if _positional(args):
        return "`hostname NAME` sets the host name"
    return None


UTILITY_CHECKS = {
    "sed": _check_sed,
    "awk": _check_awk,
    "uniq": _check_uniq,
    "hostname": _check_hostname,
}


def _check_readonly_utility(cmd: str, args: list[str]) -> str | None:
    """Per-command checks for allow-listed utilities with write modes."""
    denied = UTILITY_DENIED_FLAGS.get(cmd)
    if denied:
        flags, reason = denied
        # find's predicates are single-dash words, so match them unexpanded.
        candidates = (args if cmd == "find"
                      else _normalise_flags(args, with_value=UTILITY_VALUE_FLAGS.get(cmd, frozenset())))
        if any(a in flags for a in candidates):
            return reason
    check = UTILITY_CHECKS.get(cmd)
    return check(args) if check else None
