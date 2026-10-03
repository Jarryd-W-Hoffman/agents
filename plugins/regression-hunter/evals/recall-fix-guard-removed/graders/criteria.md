---
type: llm
weight: 1
---

The response is a regression hunt report.

Commit `018c50a` "Fix double charge when Stripe retries a webhook (#311)"
added a check that skips a Stripe event whose `provider_event_id` is already
recorded. The change moves payment recording into `PaymentRecorder` and the
check is gone: neither the controller nor `PaymentRecorder::record` has it, so
a retried webhook again creates a second Payment and a second receipt.

Score 1 only if all of these hold:
- A finding with an ID beginning `REG-` reports that the idempotency check
  (the already-recorded `provider_event_id` guard) was removed.
- It cites the fix (by `018c50a`, its subject, or #311).
- Its failure scenario is a retried webhook recording a second payment or
  charging or emailing the customer twice.
- Its severity is critical or major.

Wording does not matter. Do not penalise other findings.
