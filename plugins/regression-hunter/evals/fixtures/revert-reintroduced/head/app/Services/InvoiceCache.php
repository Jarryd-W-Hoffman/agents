<?php

namespace App\Services;

use App\Models\Invoice;
use Illuminate\Support\Facades\Cache;

class InvoiceCache
{
    public function get(int $id): Invoice
    {
        return Cache::tags(['invoices'])->remember("invoice:{$id}", 3600, fn () => Invoice::with('lines')->findOrFail($id));
    }

    public function forget(int $id): void
    {
        Cache::tags(['invoices'])->forget("invoice:{$id}");
    }

    // EVAL: seeded regression -- re-introduces the tags reverted in INC-142; the file store has no tags
    public function flushAll(): void
    {
        Cache::tags(['invoices'])->flush();
    }
}
