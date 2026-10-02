<?php

namespace App\Services;

use App\Models\Invoice;

class InvoiceService
{
    public function total(Invoice $invoice): int
    {
        return $invoice->lines->sum('amount_cents');
    }
}
