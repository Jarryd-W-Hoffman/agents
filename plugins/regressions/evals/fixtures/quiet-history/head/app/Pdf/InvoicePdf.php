<?php

namespace App\Pdf;

use App\Models\Invoice;

class InvoicePdf
{
    public function header(Invoice $invoice): array
    {
        return [
            'number' => $invoice->number,
            'date' => $invoice->issued_at->toDateString(),
            'customer' => $invoice->customer->name,
            'company' => $invoice->customer->company_name,
        ];
    }
}
