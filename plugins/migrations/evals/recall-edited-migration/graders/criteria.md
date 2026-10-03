---
type: llm
weight: 1
---

The response is a migration safety report.

The change edits `2026_04_01_000000_create_invoices_table.php`, a migration
that already existed at base and so has already run in production, to add a
`reference` column. Production will never run the edit, so the column will not
exist there while the new code writes `reference`; fresh installs and CI will
have it, so the schemas diverge.

Score 1 only if all of these hold:
- A finding with an ID beginning `MIG-` reports that an existing (already-run)
  migration was modified rather than a new migration added.
- It says the change will not reach production databases (or that schemas will
  drift between production and fresh installs), and/or that the new code will
  fail writing a column that does not exist in production.
- Its severity is critical or major.
- It recommends (or clearly implies) adding a new migration instead of editing
  the old one.

Wording does not matter.
