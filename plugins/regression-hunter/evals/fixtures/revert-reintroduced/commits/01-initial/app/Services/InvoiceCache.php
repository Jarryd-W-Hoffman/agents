<?php

namespace App\Services;

use App\Models\Invoice;
use Illuminate\Support\Facades\Cache;

class InvoiceCache
{
    public function get(int $id): Invoice
    {
        return Cache::remember("invoice:{$id}", 3600, fn () => Invoice::with('lines')->findOrFail($id));
    }

    public function forget(int $id): void
    {
        Cache::forget("invoice:{$id}");
    }
}
