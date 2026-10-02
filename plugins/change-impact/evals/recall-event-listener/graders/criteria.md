---
type: llm
weight: 1
---

The response is a change impact map for a change that renames the
`OrderPlaced` event's constructor property from `total` (float) to
`totalCents` (int).

Score 1 only if all of these hold:
- The map lists the `SendOrderConfirmation` listener as reached, found
  through the `$listen` array in `EventServiceProvider`.
- The map records that the listener is queued (`ShouldQueue`) and that the
  event's payload is a contract: events already serialized on the queue, or
  listeners deployed separately, see the old shape. This can appear under
  Contracts, Risks or Entry points, in any wording.
- The map lists `POST /checkout` (`CheckoutController::store`) as an entry
  point that dispatches the event.

It does not need to say whether the listener is buggy. Ignore wording,
section order and the limits section.
