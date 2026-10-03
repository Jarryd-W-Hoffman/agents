---
type: llm
weight: 1
---

The response is a regression hunt report.

The change re-adds `Cache::tags(['invoices'])` to `InvoiceCache`. That is what
commit `9cd4442` ("Use cache tags so all invoice entries can be flushed at
once") did, and commit `fcacd17` reverted it because production uses the file
cache store, which does not support tags: every invoice page threw
BadMethodCallException (INC-142). `config/cache.php` still defaults to the
file store at head.

Score 1 only if all of these hold:
- A finding with an ID beginning `REG-` reports that the change
  re-introduces the reverted cache tags.
- It cites the revert (by `fcacd17`, its subject, or INC-142) and the reason:
  the file cache store does not support tags.
- Its severity is critical or major.

Wording does not matter. Do not penalise other findings.
