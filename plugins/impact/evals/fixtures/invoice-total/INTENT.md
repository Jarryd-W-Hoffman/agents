# Change intent

Apply invoice-level discounts: `InvoiceService::total` now subtracts the
invoice's `discount_cents` from the sum of its lines.
