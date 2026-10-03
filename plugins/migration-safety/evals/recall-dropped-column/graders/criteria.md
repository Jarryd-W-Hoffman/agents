---
type: llm
weight: 1
---

The response is a migration safety report.

It MUST report that the new migration drops `customers.legacy_email` while the
base release, which keeps serving traffic during the deploy, still uses it:
`CustomerController::show` reads `$customer->legacy_email` and `store` writes
it (and the base `Customer` model lists it in `$fillable`).

Score 1 only if all of these hold:
- A finding with an ID beginning `MIG-` reports the drop of `legacy_email`.
- Its failure scenario says the previous/base/old code still reads or writes
  the column during the deploy window, so customer requests fail after the
  migration runs and before the new release is live.
- Its severity is critical or major, not minor.

Wording does not matter. Do not require exact line numbers. Do not penalise
other findings, as long as this one is present. A suggested fix of splitting
the change across two releases (expand and contract) is correct but not
required.
