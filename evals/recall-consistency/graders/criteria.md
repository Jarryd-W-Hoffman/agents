---
type: llm
weight: 1
---

The response is a four-pass review report.

Three sibling files establish a convention: a class named `<Thing>Repository`,
a `find_by_*` lookup method, and logging through `log_event` from
`logging_helper`. `pallet_repository.py` departs on all three: `PalletRepo`,
`get`, and the stdlib `logging` module.

Score 1 only if all of these hold:
- At least one of those three departures is reported as a finding.
- It is attributed to the **consistency** pass (a finding ID beginning `CNS-`).
- The finding cites the sibling files as the in-repo precedent, rather than
  appealing to general style preference.

Wording does not matter. Other findings do not reduce the score.
