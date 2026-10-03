#!/usr/bin/env python3
"""Tests for hooks/readonly-guard.py. Run: python3 tests/test_readonly_guard.py"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(REPO, "hooks", "readonly-guard.py")

spec = importlib.util.spec_from_file_location("readonly_guard", GUARD)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)  # type: ignore[union-attr]


def bash(cmd: str) -> str:
    return guard.classify_bash(cmd)[0]


def mcp(name: str) -> str:
    return guard.classify_mcp(name)[0]


class BashAllow(unittest.TestCase):
    ALLOWED = [
        "git status",
        "git diff HEAD",
        "git diff main...HEAD --stat",
        "git log --oneline -20 -- CHANGELOG.md",
        "git log --format='%s%n%b' main..HEAD",
        "git blame -L 10,20 src/app.ts",
        "git show abc123:path/to/file.php",
        "git fetch origin feature/x",
        "git branch --show-current",
        "git branch -a",
        "git tag -l 'v*'",
        "git remote -v",
        "git stash list",
        "git config --get remote.origin.url",
        "git symbolic-ref refs/remotes/origin/HEAD",
        "git ls-files '*CLAUDE.md'",
        # --no-* turns the external-command behaviour off, so it stays a read
        "git diff --no-ext-diff main...HEAD",
        "git log --no-textconv -p",
        # the options that look like denied ones are reads: `--text` is a real
        # option, not an abbreviation of `--textconv`; `-O<file>` on a diff
        # orders files and `-u` on log is a patch; a bare `--` ends options
        "git diff --text main...HEAD",
        "git log -O order.txt -p",
        "git log -u -1",
        "git grep -n TODO -- src",
        "git grep -e TODO HEAD",
        "git ls-remote --heads origin",
        "git cat-file -p HEAD",
        "git fetch --dry-run origin",
        # a version check is a read when it is the only argument
        "python3 --version",
        "node --version",
        "node -V",
        "npm --version",
        "go version",
        "docker version",
        "git merge-base main HEAD",
        "git -C /tmp/repo log -3",
        "git --no-pager diff",
        "git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown",
        "git diff $(git merge-base main HEAD)...HEAD",
        "gh pr view 142 --json title,body",
        "gh pr diff 142",
        "gh pr checks 142",
        "gh issue view 99 --comments",
        "gh api repos/o/r/pulls/1/comments",
        "gh api -X GET repos/o/r/pulls/1",
        "gh run list --limit 5",
        "gh search prs --repo o/r 'export'",
        "glab mr view 12",
        "glab api projects/1/merge_requests/2",
        "jira issue view PROJ-123",
        "jira issue list --project PROJ",
        "acli jira workitem view --key PROJ-1",
        "linear issue list --label bug",
        "linear issue list",
        "lin issue get ENG-42",
        "aws s3 ls s3://bucket/",
        "curl -s https://api.example.com/issues/1",
        "ls -la src/",
        "cat README.md | head -50",
        "grep -rn 'fetchUser' src/ | wc -l",
        "find . -name '*.php' -not -path './vendor/*'",
        "sed -n 1,40p src/app.ts",
        "jq '.scripts' package.json",
        "cat file.log 2>&1 | tail -20",
        "FOO=bar git status",
        "time git log -1",
        "cd src && git status",
        "echo 'a > b' | wc -c",
        "grep '>' file.txt",
        "rg 'TODO|FIXME' --glob '!vendor'",
        "wc -l < file.txt",
        # multi-line commands
        "git status\ngit diff",
        "echo 'a\nb' | wc -l",
        "git log \\\n  --oneline -5",
        # redirects
        "git rev-parse HEAD 2>/dev/null",
        "git status 2>/dev/null 1>/dev/null",
        "cat file.log 2>&1|tail -20",
        # quoted process substitution is just text
        "grep '<(' file",
        # env as a wrapper
        "env",
        "env FOO=1 git status",
        "env -i git status",
        "env -u FOO git status",
        # gh api and HTTP clients
        "gh api -XGET repos/o/r/pulls/1",
        "gh api --method=GET repos/o/r/pulls/1",
        "gh api --method GET repos/o/r/pulls/1",
        "gh api --paginate repos/o/r/pulls/1/comments --jq '.[].body'",
        "gh api -H 'Accept: application/vnd.github+json' repos/o/r/pulls/1",
        "gh api -i repos/o/r/pulls/1",
        "curl -sSL https://api.example.com/issues/1",
        "curl -XGET https://api.example.com/issues/1",
        "curl --request HEAD https://api.example.com/issues/1",
        "curl -s -H 'Accept: application/json' -u user:tok https://api.example.com/x",
        "curl -s -m 10 --retry 3 -w '%{http_code}' https://api.example.com/x",
        "curl -sI https://api.example.com/x",
        "http --ignore-stdin https://x/issues",
        "http --ignore-stdin GET https://x q==1",
        "xh -I --print=b https://x",
        "http --ignore-stdin https://x Accept:application/json",
        # read verbs
        "aws s3 ls s3://bucket/",
        # utilities in their read-only forms
        "sed -n '/hello/p' file",
        "sed 's/a/b/g' f",
        "sed -E 's/(a)/\\1/' f",
        "sed -e 's/a/b/' -e 's/c/d/' f",
        "awk '{print $1}' f",
        "awk -F: '{print $2}' /etc/passwd",
        "awk -F'|' '{print $1}' f",
        "sort -u file",
        "uniq -c file",
        "yq '.a' file.yml",
        "tree -L 2 src",
        "less -N file",
        "fd -e php Controller",
        "rg -n foo src",
        "date +%s",
        "hostname",
        "find . -type f -print0",
        # git
        "git reflog",
        "git reflog show -5",
        "git diff --stat",
        "git fetch origin",
        "git fetch --all",
        "git fetch origin pull/12/head",
        "git branch --contains abc",
        "git config --list",
        "git --git-dir=.git status",
        "git fsck",
        "git tag -l --sort=-creatordate",
        "git branch -r --format='%(refname)'",
        "git log -Sfoo --oneline",
        "git symbolic-ref -q HEAD",
        "awk -v n=1 '{print $n}' f",
        "sed -n '2,5p;10p' file",
        # dangerous environment variables: harmless ones still pass
        "GIT_PAGER=cat git log -1",
        "GH_REPO=o/r gh pr view 1",
        "LC_ALL=C git status",
        # wrappers with values, safe redirects, sed/awk scanners
        "nice -n 10 git log",
        "nice -n10 git log",
        "ionice -c 3 git log",
        "time -p git log -1",
        "caffeinate -t 60 git log",
        "git remote 2>/dev/null",
        "git symbolic-ref HEAD 2>/dev/null",
        "git branch -a 2>/dev/null",
        "curl -si https://api.example.com/x",
        "sed 's/e/x/' f",
        "sed 's/ w / W /' f",
        "sed 's/a\\/e/x/' f",
        "sed -n '/error/Ip' f",
        "sed '0~3d' f",
        "sed '5!d' f",
        "sed 'y/abc/xyz/' f",
        "sed 'q5' f",
        "sed 's/x/y/2g' f",
        "sed '/x/{s/a/b/;p}' f",
        "sed 's/[[:space:]]*$//' f",
        "sed -e 's/a/e/' -e 's/b/w/' f",
        "sed 's/a/b/g;t;s/e/f/' f",
        "awk 'NR>5' f",
        "awk '$3 > 100 {print $1}' f",
        "awk '/foo|bar/' f",
        "awk '$1 == \"a\" || $2 == \"b\"' f",
        "awk '{print \"a > b\"}' f",
        "awk '{print (a > b) ? 1 : 0}' f",
        "awk '{ if ($1 > 5) print $1 }' f",
        "awk '{gsub(/a\\/b/, \"x\"); print}' f",
        "awk '{getline; print}' f",
        "awk '{print $1/$2}' f",
        # option values must not be read as the script, the program or another flag
        "date -Iseconds",
        "date -I",
        "date -d '+1 day'",
        "sed -l 60 's/a/b/' f",
        "awk --assign n=1 '{print $n}' f",
        "awk --field-separator : '{print $2}' f",
        # HTTPie only guarantees a GET when stdin is ignored
        "http --ignore-stdin HEAD https://x",
        "xh --ignore-stdin https://x",
        # curl --write-out prints transfer info
        "curl -s -w '%{http_code}' https://x",
        # an escaped quote is a literal character, not a delimiter
        'echo "a \\" b > c" | wc -c',
    ]

    def test_allowed(self):
        for cmd in self.ALLOWED:
            with self.subTest(cmd=cmd):
                self.assertEqual(bash(cmd), "allow", guard.classify_bash(cmd)[1])


class BashDeny(unittest.TestCase):
    DENIED = [
        # `--ext-diff` runs `diff.external`; `--textconv` runs a textconv
        # filter. Both take the command from config, exactly as
        # GIT_EXTERNAL_DIFF and `git -c diff.external=` do.
        "git log --ext-diff",
        "git diff --ext-diff main...HEAD",
        "git show --ext-diff HEAD",
        "git log --textconv -p",
        "git grep --textconv TODO",
        # options of read-only subcommands that run the command they are given
        "git grep -O'touch x' -e TODO",
        "git grep -O 'touch x' -e TODO",
        "git grep -nO'touch x' -e TODO",
        "git grep --open-files-in-pager='touch x' -e TODO",
        "git fetch --upload-pack='touch x' origin",
        "git fetch origin --upload-pack 'touch x'",
        "git ls-remote --upload-pack='touch x' origin",
        "git ls-remote -u 'touch x' origin",
        "git cat-file --filters HEAD:file",
        # git accepts any unambiguous prefix of a long option, so denied
        # options are denied however they are abbreviated
        "git grep --open='touch x' -e TODO",
        "git grep --textc TODO",
        "git fetch --upload-p='touch x' origin",
        "git ls-remote --upload='touch x' origin",
        "git fetch --for origin",
        "git fetch --pru origin",
        "git diff --ext-d HEAD",
        # the version allowance is single-argument only
        "python3 --version -c 'import os; os.remove(\"x\")'",
        "python3 --version extra",
        "python3 -v",
        # `npm version 1.2.3` bumps package.json, so more than one argument
        # is never a version check
        "npm version 1.2.3",
        "go version -m ./bin",
        "go build ./...",
        "git add .",
        "git commit -m x",
        "git push origin main",
        "git checkout main",
        "git switch -c feature",
        "git reset --hard",
        "git rebase main",
        "git merge feature",
        "git stash",
        "git stash pop",
        "git branch new-branch",
        "git branch -D old",
        "git tag v1.0.0",
        "git remote add up https://x",
        "git config user.name bob",
        "git symbolic-ref HEAD refs/heads/x",
        "git worktree add ../x",
        "git clean -fd",
        "git apply patch.diff",
        "git cherry-pick abc",
        "git notes add -m x",
        "gh pr comment 142 --body hi",
        "gh pr create --fill",
        "gh pr merge 142",
        "gh pr checkout 142",
        "gh pr review 142 --approve",
        "gh pr edit 142 --title x",
        "gh issue create --title x",
        "gh issue close 99",
        "gh api -X POST repos/o/r/issues -f title=x",
        "gh api --method PATCH repos/o/r/issues/1",
        "gh api repos/o/r/issues --input body.json",
        "glab mr merge 12",
        "glab mr note 12 -m hi",
        "jira issue create --summary x",
        "jira issue comment add PROJ-1 'hi'",
        "jira issue assign PROJ-1 me",
        "jira issue move PROJ-1 Done",
        "jira issue edit PROJ-1",
        "linear issue create --title x",
        "linear issue update ENG-1 --state done",
        "aws s3 cp file s3://bucket/",
        "aws s3 rm s3://bucket/x",
        "curl -X POST https://api.example.com/issues",
        "curl -d '{}' https://api.example.com/issues",
        "curl -o out.json https://api.example.com/x",
        "curl -X DELETE https://api.example.com/x",
        "rm -rf build",
        "mv a b",
        "cp a b",
        "touch x",
        "mkdir -p x",
        "chmod +x script.sh",
        "echo hi > file.txt",
        "cat a >> b",
        "git log > log.txt",
        "cat file | tee out.txt",
        "sed -i 's/a/b/' file",
        "sed -i.bak 's/a/b/' file",
        "find . -name '*.tmp' -delete",
        "find . -name '*.js' -exec rm {} \\;",
        "awk '{print > \"out\"}' file",
        "python3 script.py",
        "node -e 'require(\"fs\").writeFileSync(\"x\",\"y\")'",
        "php artisan migrate",
        "npm install",
        "composer install",
        "npx prettier --write .",
        "make build",
        "docker run x",
        "kubectl delete pod x",
        "sudo ls",
        "bash -c 'rm -rf x'",
        "sh -c 'echo hi'",
        "eval 'rm x'",
        "xargs rm < files.txt",
        "source ~/.zshrc",
        "git status; rm -rf x",
        "git status && echo hi > x",
        "ls || rm x",
        "ls | xargs rm",
        "echo `rm x`",
        "$(rm x)",
        "unknown-tool --flag",
        "psql -c 'DROP TABLE x'",
        "ssh host 'ls'",
        "open https://example.com",
        "cat 'unbalanced",
        # multi-line commands
        "git status\nrm -rf x",
        "ls\ngit push origin main",
        "pwd\npython3 script.py",
        # fd-prefixed and &> redirects
        "git log &> /tmp/out.txt",
        "git diff 1> diff.patch",
        "cat x 2> errors.log",
        "ls &>> log",
        # process substitution
        "cat <(rm -rf build)",
        "diff <(ls a) <(ls b)",
        "tee >(cat)",
        # env executes its arguments
        "env rm x",
        "/usr/bin/env node -e 'x'",
        "env FOO=1 python3 script.py",
        "env -S 'rm x'",
        # attached and --long=value flag spellings
        "wget https://example.com/x.json",
        "wget -O - https://example.com/x.json",
        "curl -sSLO https://x/f.tgz",
        "curl -XPOST https://x",
        "curl -d'{}' https://x",
        "curl --json '{\"a\":1}' https://x",
        "curl --data-raw=x https://x",
        "curl -o out https://x",
        "curl -c jar https://x",
        "curl -T file https://x",
        "curl -F 'f=@x' https://x",
        "curl --output-dir d https://x",
        "curl -D headers.txt https://x",
        "curl -K config https://x",
        "curl -s --unknown-flag https://x",
        "gh api -XPOST repos/o/r/issues --field=title=x",
        "gh api repos/o/r/issues -fbody=hi",
        "gh api --method=POST repos/o/r/x",
        "gh api graphql -f query='{ viewer { login } }'",
        "gh api -F body=@file repos/o/r/issues/1/comments",
        "gh api -XDELETE repos/o/r/issues/1",
        "http https://x/issues title=x",
        "http POST https://x",
        "xh https://x/a name:=1",
        "http --download https://x/f",
        "http https://x file@./a.txt",
        "http -o out https://x",
        # download/export write files
        "az storage blob download --file out.bin --name x --container c",
        "gcloud sql export sql inst gs://b/f",
        # utilities with write modes
        "sed -Ei 's/a/b/' file",
        "sed -ni 'p' file",
        "sed --in-place=.bak 's/a/b/' file",
        "sed -f script.sed file",
        "sed 's/a/b/w out' file",
        "sed 's/a/b/gw out' file",
        "sed -n '1w out' file",
        "sed '/x/w out' file",
        "sed 'e rm x' file",
        "sed -e 's/a/b/' -e 'w out' file",
        "awk 'BEGIN{print \"rm x\" | \"sh\"}'",
        "awk '{\"date\" | getline d; print d}'",
        "awk 'BEGIN{system(\"rm x\")}'",
        "awk -f prog.awk f",
        "sort -o out file",
        "sort -oout file",
        "sort --output out file",
        "sort --output=out file",
        "uniq in out",
        "yq -i '.a = 1' file.yml",
        "yq --inplace '.a = 1' file.yml",
        "yq -Pi '.a' file.yml",
        "tree -o out.txt",
        "less -o log file",
        "less --log-file=log file",
        "fd -x rm",
        "fd --exec rm",
        "fd -X rm",
        "fd --exec-batch rm",
        "rg --pre cmd foo",
        "rg --pre=cmd foo",
        "date -s '2026-01-01'",
        "date --set='2026-01-01'",
        "hostname newname",
        "find . -fprint0 out",
        "find . -fls out",
        # git refs, files and global options
        "git reflog expire --expire=now --all",
        "git reflog delete HEAD@{1}",
        "git diff --output=f.patch",
        "git log --output f",
        "git fetch origin +feature/x:feature/x",
        "git fetch origin main:main",
        "git fetch -p origin",
        "git fetch --force origin x",
        "git fetch --tags origin",
        "git fetch --depth=1 origin",
        "git symbolic-ref -d refs/heads/x",
        "git symbolic-ref --delete refs/heads/x",
        "git branch --set-upstream-to=origin/x",
        "git branch -f main HEAD~1",
        "git branch --track x origin/x",
        "git config --get x --unset y",
        "git config --edit",
        "git config --list --add x y",
        "git -c diff.external='rm -rf' diff",
        "git -c core.pager=rm log",
        "git --config-env=diff.external=X diff",
        "git --exec-path=/tmp status",
        "git fsck --lost-found",
        # dangerous environment-variable prefixes
        "GIT_EXTERNAL_DIFF=/bin/rm git diff",
        "PATH=/tmp git status",
        "PAGER='rm x' git log",
        "LD_PRELOAD=/tmp/x.so ls",
        "DYLD_INSERT_LIBRARIES=/tmp/x.dylib ls",
        "GIT_CONFIG_GLOBAL=/tmp/cfg git status",
        "env GIT_EXTERNAL_DIFF=/bin/rm git diff",
        "env PAGER=less git log",
        # wrappers with values, safe redirects, sed/awk scanners
        "nice -n 10 rm x",
        "ionice -c 3 -n 7 rm x",
        "time -o t.txt git log",
        "git remote 2>/dev/null; rm x",
        "sed 's/a/b/;w out' f",
        "sed '1{s/a/b/;w out}' f",
        "sed '\\,x,w out' f",
        "sed '/a/I w out' f",
        "sed 's/a/b/2w out' f",
        "sed 's/a/b/ge' f",
        "sed '1,3w out' f",
        "sed '2!w out' f",
        "sed 's/a/b' f",
        "sed 'k' f",
        "awk '{printf \"%s\", $1 > \"out\"}' f",
        "awk '{print $1, $2 > $3}' f",
        "awk -e '{print | \"sh\"}' f",
        "awk '{print (a>b) > \"f\"}' f",
        "awk 'NR>5 {print > \"f\"}' f",
        "awk '{x = \"/\"; print $1 | \"sh\"}' f",
        # escaped quotes do not hide a redirect
        'echo \\"a > out \\"b',
        "echo \\'a > out \\'b",
        # HTTPie/xh POST whatever is on stdin unless it is ignored
        "http https://x/issues",
        "xh https://x/issues",
        "cat body.json | http https://x",
        "http https://x < body.json",
        "http PURGE https://x",
        # curl --write-out can write a file
        "curl -s -w '%output{/tmp/x}%{json}' https://x",
        "curl --write-out='%output{>>f}' https://x",
        # sed -I is in-place on BSD/macOS; -l takes a value
        "sed -I '' 's/a/b/' file",
        "sed -I.bak 's/a/b/' file",
        "sed -l 5 'w out' file",
        "sed --line-length=5 'w out' file",
        # gawk long options take a value; -p/-o/-d write files, -E/-l load code
        "awk --assign x=1 '{print > \"out\"}' file",
        "awk --field-separator : '{print > \"out\"}' f",
        "awk -p '{print}' file",
        "awk -d '{print}' file",
        "awk -o '{print}' f",
        "awk -E prog.awk f",
        "awk -l ext '{print}' f",
        "awk -i inplace '{print}' f",
        # attached value on a denied git global option
        "git -cdiff.external=rm diff",
    ]

    def test_denied(self):
        for cmd in self.DENIED:
            with self.subTest(cmd=cmd):
                self.assertEqual(bash(cmd), "deny", f"should deny: {cmd}")


class McpClassification(unittest.TestCase):
    def test_allow_reads(self):
        for name in [
            "mcp__github__get_pull_request",
            "mcp__github__list_pull_requests",
            "mcp__github__search_issues",
            "mcp__github__pull_request_read",
            "mcp__github__get_file_contents",
            "mcp__github__list_commits",
            "mcp__github__get_pull_request_reviews",
            "mcp__github__get_release_by_tag",
            "mcp__github__list_workflow_runs",
            "mcp__gitlab__get_merge_request",
            "mcp__github__get_issue_comments",
            "mcp__github__get_label",
            "mcp__atlassian__getJiraIssue",
            "mcp__atlassian__searchJiraIssuesUsingJql",
            "mcp__atlassian__getConfluencePage",
            "mcp__linear__get_issue",
            "mcp__linear__list_issues",
            "mcp__linear__list_comments",
            "mcp__linear__search_documentation",
            "mcp__sentry__find_issues",
            "mcp__sentry__get_issue_details",
            "mcp__context7__get-library-docs",
            "mcp__slack__search_messages",
            "mcp__notion__fetch",
        ]:
            with self.subTest(name=name):
                self.assertEqual(mcp(name), "allow", guard.classify_mcp(name)[1])

    def test_deny_writes(self):
        for name in [
            "mcp__github__create_issue",
            "mcp__github__add_issue_comment",
            "mcp__github__create_pull_request_review",
            "mcp__github__merge_pull_request",
            "mcp__github__update_pull_request",
            "mcp__github__push_files",
            "mcp__github__create_or_update_file",
            "mcp__github__fork_repository",
            "mcp__github__pull_request_review_write",
            "mcp__github__delete_file",
            "mcp__atlassian__createJiraIssue",
            "mcp__atlassian__editJiraIssue",
            "mcp__atlassian__addCommentToJiraIssue",
            "mcp__atlassian__transitionJiraIssue",
            "mcp__atlassian__createConfluencePage",
            "mcp__linear__create_issue",
            "mcp__linear__update_issue",
            "mcp__linear__create_comment",
            "mcp__linear__save_issue",
            "mcp__slack__post_message",
            "mcp__slack__send_message",
            "mcp__chrome-devtools__navigate_page",
            "mcp__chrome-devtools__click",
            "mcp__chrome-devtools__fill_form",
            "mcp__chrome-devtools__evaluate_script",
            "mcp__github__dispatch_workflow",
            "mcp__github__run_workflow",
            "mcp__github__assign_copilot_to_issue",
            "mcp__github__mark_all_notifications_read",
            "mcp__sentry__resolve_issue",
            "mcp__github__get_and_update_issue",
            "mcp__github__download_workflow_run_artifact",
            "mcp__confluence__export_page",
        ]:
            with self.subTest(name=name):
                self.assertEqual(mcp(name), "deny", f"should deny: {name}")

    def test_deny_unclassifiable(self):
        self.assertEqual(mcp("mcp__foo__frobnicate"), "deny")


class EndToEnd(unittest.TestCase):
    def run_guard(self, payload: dict, env: dict | None = None) -> dict | None:
        full_env = dict(os.environ)
        for k in ("READONLY_GUARD_ALLOW", "READONLY_GUARD_DENY", "READONLY_GUARD_AGENTS",
                  "READONLY_GUARD_STRICT", "READONLY_GUARD_DEBUG"):
            full_env.pop(k, None)
        full_env.update(env or {})
        proc = subprocess.run(
            [sys.executable, GUARD], input=json.dumps(payload).encode(),
            capture_output=True, env=full_env, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        out = proc.stdout.decode().strip()
        return json.loads(out) if out else None

    def decision(self, payload, env=None):
        out = self.run_guard(payload, env)
        return None if out is None else out["hookSpecificOutput"]["permissionDecision"]

    def test_edit_denied(self):
        self.assertEqual(self.decision({"tool_name": "Edit", "tool_input": {"file_path": "x"}}), "deny")

    def test_write_denied(self):
        self.assertEqual(self.decision({"tool_name": "Write", "tool_input": {"file_path": "x"}}), "deny")

    def test_read_deferred(self):
        self.assertIsNone(self.decision({"tool_name": "Read", "tool_input": {"file_path": "x"}}))

    def test_bash_allow_and_deny(self):
        self.assertEqual(self.decision({"tool_name": "Bash", "tool_input": {"command": "git diff HEAD"}}), "allow")
        self.assertEqual(self.decision({"tool_name": "Bash", "tool_input": {"command": "git push"}}), "deny")

    def test_mcp(self):
        self.assertEqual(self.decision({"tool_name": "mcp__github__get_pull_request", "tool_input": {}}), "allow")
        self.assertEqual(self.decision({"tool_name": "mcp__github__create_issue", "tool_input": {}}), "deny")

    def test_env_overrides(self):
        self.assertEqual(self.decision(
            {"tool_name": "mcp__foo__frobnicate", "tool_input": {}},
            {"READONLY_GUARD_ALLOW": "mcp__foo__*"}), "allow")
        self.assertEqual(self.decision(
            {"tool_name": "Bash", "tool_input": {"command": "git diff"}},
            {"READONLY_GUARD_DENY": "git diff*"}), "deny")
        # deny wins over allow
        self.assertEqual(self.decision(
            {"tool_name": "mcp__foo__get_thing", "tool_input": {}},
            {"READONLY_GUARD_ALLOW": "mcp__foo__*", "READONLY_GUARD_DENY": "mcp__foo__*"}), "deny")

    def test_agent_scope(self):
        env = {"READONLY_GUARD_AGENTS": "*-reviewer"}
        self.assertIsNone(self.decision(
            {"tool_name": "Write", "tool_input": {}, "agent_type": "general-purpose"}, env))
        self.assertEqual(self.decision(
            {"tool_name": "Write", "tool_input": {}, "agent_type": "correctness-reviewer"}, env), "deny")
        self.assertEqual(self.decision(
            {"tool_name": "Write", "tool_input": {}, "agent_type": "four-pass-review:correctness-reviewer"}, env), "deny")

    def test_malformed_input_fails_closed(self):
        proc = subprocess.run([sys.executable, GUARD], input=b"not json", capture_output=True, check=False)
        self.assertEqual(proc.returncode, 0)
        self.assertIn('"deny"', proc.stdout.decode())

    def test_no_agent_identity_defers_by_default(self):
        # The main session's own calls look like this; the guard must not touch them.
        env = {"READONLY_GUARD_AGENTS": "*-reviewer"}
        self.assertIsNone(self.decision(
            {"tool_name": "Bash", "tool_input": {"command": "rm -rf build"}}, env))

    def test_no_agent_identity_denies_under_strict(self):
        env = {"READONLY_GUARD_AGENTS": "*-reviewer", "READONLY_GUARD_STRICT": "1"}
        self.assertEqual(self.decision(
            {"tool_name": "Bash", "tool_input": {"command": "rm -rf build"}}, env), "deny")

    def test_no_agent_identity_is_reported_under_debug(self):
        env = {"READONLY_GUARD_AGENTS": "*-reviewer", "READONLY_GUARD_DEBUG": "1"}
        full_env = dict(os.environ)
        full_env.update(env)
        proc = subprocess.run(
            [sys.executable, GUARD],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm -rf build"}}).encode(),
            capture_output=True, env=full_env, check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("no agent identity", proc.stderr.decode())

    def test_scope_survives_a_renamed_envelope_key(self):
        # If the PreToolUse envelope ever renames `agent_type`, an agent-shaped
        # key still resolves, so the guard keeps enforcing instead of no-opping.
        env = {"READONLY_GUARD_AGENTS": "*-reviewer"}
        for key in ("agent_type", "agent_name", "subagent_type", "agentType", "sub_agent_name"):
            with self.subTest(key=key):
                self.assertEqual(self.decision(
                    {"tool_name": "Write", "tool_input": {}, key: "correctness-reviewer"}, env),
                    "deny")

    def test_runs_from_any_working_directory(self):
        # hooks.json invokes the guard by absolute path, so its cwd is whatever
        # the session happens to be in. The entry point imports the `guard`
        # package beside it, which only resolves because it puts its own
        # directory on sys.path -- this is the test that says so.
        full_env = dict(os.environ)
        full_env["READONLY_GUARD_AGENTS"] = "*-reviewer"
        payload = {"tool_name": "Bash", "tool_input": {"command": "rm -rf x"},
                   "agent_type": "correctness-reviewer"}
        with tempfile.TemporaryDirectory() as elsewhere:
            proc = subprocess.run(
                [sys.executable, GUARD], input=json.dumps(payload).encode(),
                capture_output=True, env=full_env, cwd=elsewhere, check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertIn('"deny"', proc.stdout.decode())

    def test_selftest_passes(self):
        full_env = dict(os.environ)
        full_env["READONLY_GUARD_AGENTS"] = "*-reviewer"
        proc = subprocess.run([sys.executable, GUARD, "--selftest"],
                              capture_output=True, env=full_env, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout.decode() + proc.stderr.decode())
        self.assertIn("selftest: passed", proc.stdout.decode())


class AgentIdentity(unittest.TestCase):
    def test_known_keys(self):
        self.assertEqual(guard._agent_identity({"agent_type": "correctness-reviewer"}),
                         "correctness-reviewer")
        self.assertEqual(guard._agent_identity({"subagent_type": "x-reviewer"}), "x-reviewer")

    def test_blank_and_missing_are_none(self):
        self.assertIsNone(guard._agent_identity({}))
        self.assertIsNone(guard._agent_identity({"agent_type": ""}))
        self.assertIsNone(guard._agent_identity({"agent_type": "   "}))
        self.assertIsNone(guard._agent_identity({"agent_type": None}))

    def test_unknown_but_agent_shaped_key(self):
        self.assertEqual(guard._agent_identity({"agentName": "correctness-reviewer"}),
                         "correctness-reviewer")

    def test_agent_id_alone_is_not_an_identity(self):
        # An opaque id does not match a `*-reviewer` glob, so it must not be
        # mistaken for the agent's type.
        self.assertIsNone(guard._agent_identity({"agent_id": "a1b2c3"}))


if __name__ == "__main__":
    unittest.main(verbosity=1)
