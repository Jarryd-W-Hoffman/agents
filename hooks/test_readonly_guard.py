#!/usr/bin/env python3
"""Tests for hooks/readonly-guard.py. Run: python3 hooks/test_readonly_guard.py"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "readonly-guard.py")

spec = importlib.util.spec_from_file_location("guard", GUARD)
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
    ]

    def test_allowed(self):
        for cmd in self.ALLOWED:
            with self.subTest(cmd=cmd):
                self.assertEqual(bash(cmd), "allow", guard.classify_bash(cmd)[1])


class BashDeny(unittest.TestCase):
    DENIED = [
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
        ]:
            with self.subTest(name=name):
                self.assertEqual(mcp(name), "deny", f"should deny: {name}")

    def test_deny_unclassifiable(self):
        self.assertEqual(mcp("mcp__foo__frobnicate"), "deny")


class EndToEnd(unittest.TestCase):
    def run_guard(self, payload: dict, env: dict | None = None) -> dict | None:
        full_env = dict(os.environ)
        for k in ("READONLY_GUARD_ALLOW", "READONLY_GUARD_DENY", "READONLY_GUARD_AGENTS"):
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


if __name__ == "__main__":
    unittest.main(verbosity=1)
