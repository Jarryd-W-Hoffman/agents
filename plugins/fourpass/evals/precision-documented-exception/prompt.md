---
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash]
---

Run a four-pass code review of the change below.

Treat `CONVENTIONS.fixture.md` as the project's written conventions for this area. It is named with a suffix only so it is not picked up as a live instruction file.

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

Use the fourpass skill. Review the files as whole files: the change below is the whole of it.

## Change intent

Add an append-only access log, following the documented exception for audit
tables in CONVENTIONS.

## Files

### `audit/CONVENTIONS.fixture.md`

```markdown
# Conventions

- Repositories are named `<Thing>Repository` and expose `find_by_*`.
- **Exception:** append-only audit tables have no lookup API by design. They
  expose `append` only, and are named `<Thing>Log`. Do not add `find_by_*`
  to them.
```

### `audit/access_log.py`

```python
class AccessLog:
    def append(self, actor, action):
        return {"actor": actor, "action": action}
```
