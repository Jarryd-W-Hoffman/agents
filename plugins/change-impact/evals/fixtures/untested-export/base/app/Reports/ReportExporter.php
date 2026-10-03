<?php

namespace App\Reports;

class ReportExporter
{
    public function toCsv(array $rows): string
    {
        return implode("\n", array_map(fn (array $row) => implode(',', $row), $rows));
    }
}
