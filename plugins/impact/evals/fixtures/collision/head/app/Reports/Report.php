<?php

namespace App\Reports;

class Report
{
    public function generate(string $month): array
    {
        return $this->days($month)->map(fn ($day) => $day->revenue - $day->refunds)->all();
    }
}
