<?php

namespace App\Console\Commands;

use App\Reports\ReportExporter;
use App\Reports\SalesReport;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Storage;

class ExportReports extends Command
{
    protected $signature = 'reports:export {month}';

    public function handle(ReportExporter $exporter): void
    {
        $rows = SalesReport::forMonth($this->argument('month'))->rows();
        // EVAL: the only caller; no test reaches toCsv
        Storage::put("reports/{$this->argument('month')}.csv", $exporter->toCsv($rows));
    }
}
