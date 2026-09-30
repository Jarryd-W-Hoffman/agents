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

Add a repository for pallets, alongside the existing stock, supplier and
warehouse repositories.

## Files

### `inventory/logging_helper.py`

```python
def log_event(name, **fields):
    print(name, fields)
```

### `inventory/pallet_repository.py`

```python
import logging


class PalletRepo:
    def get(self, id):
        logging.getLogger(__name__).info("pallet lookup %s", id)
        return {"id": id}
```

### `inventory/stock_repository.py`

```python
from logging_helper import log_event


class StockRepository:
    def find_by_sku(self, sku):
        log_event("stock.lookup", sku=sku)
        return {"sku": sku, "qty": 0}
```

### `inventory/supplier_repository.py`

```python
from logging_helper import log_event


class SupplierRepository:
    def find_by_code(self, code):
        log_event("supplier.lookup", code=code)
        return {"code": code}
```

### `inventory/warehouse_repository.py`

```python
from logging_helper import log_event


class WarehouseRepository:
    def find_by_id(self, id):
        log_event("warehouse.lookup", id=id)
        return {"id": id}
```
