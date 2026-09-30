---
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash]
---

Run a four-pass code review of the change below.

## Review Packet (already resolved -- do not rebuild it)

Target: the change below. Review base: the files as they were before this
change. Rule base: the same revision (this is not an incremental review).
Head: the files as given here. Repository root: not applicable.

This packet is complete. There is no git repository, no checkout and no files
on disk: nothing to clone, fetch, glob, `ls` or `git` at. Skip Step 1 of the
skill entirely -- the target is resolved, the changed files are listed, the
rule sources are named below, and the change intent is given. Go straight to
briefing and launching the reviewer passes, giving each the content below in
place of diff commands.

Time spent looking for files is time not spent reviewing, and there is nothing
to find.

Use the four-pass-review skill. Review the files as whole files: the change below is the whole of it.

## Change intent

Send a notification to each user who has an email address on file. Users
without one are skipped, not an error.

## Files

### `notify/sender.py`

```python
"""Notification sending."""


def send(user, message):
    if user.email is None:
        return "skipped: no email"
    return f"sent to {user.email.lower()}: {message}"


def send_all(users, message):
    return [send(u, message) for u in users if u is not None]
```
