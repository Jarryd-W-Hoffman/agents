<?php

namespace App\Http\Controllers;

use App\Reports\Report;

class ReportController extends Controller
{
    public function show(string $month, Report $report): array
    {
        return $report->generate($month);
    }
}
