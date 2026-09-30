---
type: llm
weight: 1
---

The request asked for a single pass (`--passes correctness`).

Score 1 only if all of these hold:
- The response is a correctness report, not a merged four-pass report.
- Every finding ID begins with `COR-`. There are no `CMP-`, `CPL-` or `CNS-`
  findings.
- The null dereference on `invoice.customer` in `exporter.py` is still found.

Score 0 if the report includes the other three passes, or presents pass
summaries for passes that were not requested.
