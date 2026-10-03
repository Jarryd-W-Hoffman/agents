---
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash]
---

Run a four-pass code review of the change below.

Run **only the correctness pass** (`--passes correctness`). Do not run the other three, and do not produce a merged four-pass report.

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

Add CSV export for invoices so finance can reconcile monthly.

- `export_row` renders one invoice.
- `export_all` renders a batch.

## Files

### `billing/exporter.py`

```python
"""Invoice export. Customers are optional on API-created invoices."""


def export_row(invoice):
    return f"{invoice.id},{invoice.customer.email},{invoice.total}"


def export_all(invoices):
    return [export_row(i) for i in invoices]
```

### `billing/models.py`

```python
class Invoice:
    def __init__(self, id, total, customer=None):
        self.id = id
        self.total = total
        self.customer = customer


class Customer:
    def __init__(self, email):
        self.email = email
```
