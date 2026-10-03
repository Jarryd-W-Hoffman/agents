<?php

namespace App\Http\Controllers;

use App\Models\Invoice;

class DashboardController extends Controller
{
    public function __invoke(): array
    {
        return ['outstanding_cents' => Invoice::unpaid()->sum('total_cents')];
    }
}
