---
type: llm
weight: 1
---

The response is a four-pass review report.

It MUST report that `export_row` in `evals/fixtures/billing/exporter.py`
dereferences `invoice.customer.email` without checking whether `customer` is
`None`, even though `Invoice.customer` defaults to `None` in `models.py`.

Score 1 only if all of these hold:
- The null/None dereference on `invoice.customer` is reported as a finding.
- It is attributed to the **correctness** pass (a finding ID beginning `COR-`).
- Its severity is critical or major, not minor.
- The report states a concrete failure scenario (exporting an invoice that has
  no customer raises and breaks the export).

Wording does not matter. Do not require the exact line number. Do not penalise
the report for also raising other findings, as long as this one is present and
attributed to correctness.
