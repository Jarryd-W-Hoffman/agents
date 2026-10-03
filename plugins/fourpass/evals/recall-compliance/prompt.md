---
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash]
---

Run a four-pass code review of the change below.

Treat `CLAUDE.fixture.md` as the CLAUDE.md governing this module. It is named with a suffix only so it is not picked up as a live instruction file; for this review it is the project's written rules.

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

Add refund support to the payments module.

## Files

### `payments/CLAUDE.fixture.md`

```markdown
# Payments module rules

- **NEVER** write cardholder data or a customer's email address to logs, error
  messages, or analytics. Log the customer id only.
- All outbound HTTP MUST go through `gateway_client.request`; do not call
  `requests` or `urllib` directly from this module.
```

### `payments/gateway_client.py`

```python
def request(method, path, body):
    return {"method": method, "path": path, "body": body, "status": 200}
```

### `payments/refunds.py`

```python
import logging

from gateway_client import request

log = logging.getLogger(__name__)


def refund(customer, amount):
    log.info("refunding %s to %s", amount, customer.email)
    return request("POST", "/refunds", {"id": customer.id, "amount": amount})
```
