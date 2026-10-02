---
type: llm
weight: 1
---

The response is a change impact map for a change to `InvoiceService::total`.

Score 1 only if the map lists all of these as reached by the change (in any
section, in any wording):
- The HTTP route `GET /invoices/{invoice}` (from `routes/web.php`), reached
  through `InvoiceController::show`.
- The queued job `SendInvoiceReminder`.
- The `invoices:remind` console command (`RemindOverdueInvoices`), which
  dispatches that job, **and** its daily 08:00 schedule in `routes/console.php`.
  This is the part a name search cannot find: the schedule names the command
  by its signature string.
- The test `tests/Unit/InvoiceServiceTest.php` as covering `total`.

Score 0 if any of those four is missing, or if the map lists
`TokenService::total`, or anything that calls it, as reached by the change.

Ignore wording, section order, the risks section and the limits section.
