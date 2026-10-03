<?php

namespace App\Console\Commands;

use App\Jobs\SendInvoiceReminder;
use App\Models\Invoice;
use Illuminate\Console\Command;

class RemindOverdueInvoices extends Command
{
    protected $signature = 'invoices:remind';

    public function handle(): void
    {
        Invoice::overdue()->each(fn (Invoice $invoice) => SendInvoiceReminder::dispatch($invoice));
    }
}
