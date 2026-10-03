<?php

namespace App\Jobs;

use App\Mail\InvoiceReminder;
use App\Models\Invoice;
use App\Services\InvoiceService;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Support\Facades\Mail;

class SendInvoiceReminder implements ShouldQueue
{
    public function __construct(public Invoice $invoice)
    {
    }

    public function handle(InvoiceService $invoices): void
    {
        Mail::to($this->invoice->customer)->send(
            new InvoiceReminder($this->invoice, $invoices->total($this->invoice))
        );
    }
}
