---
type: llm
weight: 1
---

The history scan returned `"analyse": false`: no fix or revert ever touched
the changed lines. The skill must stop at that point, say there was no
history to regress, and launch no reviewer.

Score 1 only if all of these hold:
- The response says, in any wording, that the history has no fixes, reverts
  or usual partners relevant to this change, and nothing was reviewed.
- The response contains no findings with an ID beginning `REG-` and no
  report with a verdict line.

Score 0 if it reviews the change or produces findings.
