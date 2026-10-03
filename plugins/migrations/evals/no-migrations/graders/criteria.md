---
type: llm
weight: 1
---

The change touches no migration: `find-migrations.py` returned an empty
`migrations` list. The skill must stop at that point, say that there is
nothing to review, and launch no reviewer.

Score 1 only if all of these hold:
- The response says the change contains no migrations (in any wording) and
  that nothing was reviewed or there is nothing to check.
- The response contains no findings with an ID beginning `MIG-`.
- The response does not present a migration safety report with a verdict line
  and severity sections.

Score 0 if it reviews the controller change, produces findings, or writes a
report with a verdict.
