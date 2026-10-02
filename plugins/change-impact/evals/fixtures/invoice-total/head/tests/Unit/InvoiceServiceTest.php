<?php

use App\Models\Invoice;
use App\Services\InvoiceService;

it('sums the lines of an invoice', function () {
    $invoice = Invoice::factory()->hasLines(2, ['amount_cents' => 500])->create();

    expect(app(InvoiceService::class)->total($invoice))->toBe(1000);
});
