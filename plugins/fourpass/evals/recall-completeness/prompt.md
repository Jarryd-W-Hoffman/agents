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

Use the fourpass skill. Review the files as whole files: the change below is the whole of it.

## Change intent

Rename `compute_total` to `calculate_total` for consistency with the rest of
the pricing module, and update every call site.

## Files

### `orders/checkout.py`

```python
from pricing import calculate_total


def checkout(order):
    return {"total": calculate_total(order), "status": "ok"}
```

### `orders/pricing.py`

```python
def calculate_total(order):
    return sum(line.amount for line in order.lines)
```

### `orders/reports.py`

```python
from pricing import compute_total


def monthly_report(orders):
    return sum(compute_total(o) for o in orders)
```
