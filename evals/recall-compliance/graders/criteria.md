---
type: llm
weight: 1
---

The response is a four-pass review report.

The rules file says: NEVER write a customer's email address to logs.
`refunds.py` logs `customer.email`.

Score 1 only if all of these hold:
- The logging of `customer.email` is reported as a finding.
- It is attributed to the **compliance** pass (a finding ID beginning `CPL-`).
- The finding quotes or clearly paraphrases the written rule it violates, and
  points at the rules file as its source.
- Severity is critical or major (the rule is phrased NEVER).

Wording does not matter. Other findings do not reduce the score.
