---
type: llm
weight: 1
---

The response is a change impact map for a change to `Report::generate`.

The scan matched `generate` by name, so it also reported three unrelated call
sites: `InvoicePdfController` (calls `PdfRenderer::generate`),
`RotateApiTokens` (calls `TokenService::generate`) and `MakeInvite` (calls
`TokenService::generate`). None of them reaches `Report::generate`.

Score 1 only if all of these hold:
- The map lists `ReportController::show` and the route `GET /reports/{month}`
  as reaching `Report::generate`.
- The map does NOT list `InvoicePdfController`, `GET /invoices/{invoice}/pdf`,
  `RotateApiTokens` or `invites:make` / `MakeInvite` as callers or entry
  points reaching the change.

Mentioning under Limits that name collisions were found and dropped is
correct behaviour and scores 1. Score 0 also if the response contains no
impact map at all: an empty response contains no false positive, and must not
pass for that reason.
