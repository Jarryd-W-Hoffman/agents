<?php

namespace App\Reports;

class ReportExporter
{
    public function toCsv(array $rows): string
    {
        return implode("\n", array_map(fn (array $row) => implode(',', array_map(fn ($v) => '"'.str_replace('"', '""', (string) $v).'"', $row)), $rows));
    }
}
