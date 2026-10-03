---
type: llm
weight: 1
---

The response is a migration safety report.

It MUST report that the migration adds `orders.currency` as NOT NULL with no
default to an existing table, while the base release's
`CheckoutController::store` inserts orders without a currency.

Score 1 only if all of these hold:
- A finding with an ID beginning `MIG-` reports the `currency` column being
  added without `nullable()` or a `default()`.
- Its failure scenario names at least one of: inserts from the base/old code
  fail during the deploy window because no value is supplied; or the ALTER
  itself fails (or fills invalid values) because the table already has rows.
- Its severity is critical or major.

Wording does not matter. Do not require exact line numbers. Do not penalise
other findings, as long as this one is present.
