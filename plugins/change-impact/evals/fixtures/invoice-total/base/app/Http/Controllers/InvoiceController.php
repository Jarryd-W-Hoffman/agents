<?php

namespace App\Http\Controllers;

use App\Models\Invoice;
use App\Services\InvoiceService;

class InvoiceController extends Controller
{
    public function show(Invoice $invoice, InvoiceService $invoices): array
    {
        return ['id' => $invoice->id, 'total_cents' => $invoices->total($invoice)];
    }
}
