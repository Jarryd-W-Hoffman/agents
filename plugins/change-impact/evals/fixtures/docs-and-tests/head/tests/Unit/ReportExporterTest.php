<?php

use App\Reports\ReportExporter;

it('quotes fields', function () {
    expect((new ReportExporter)->toCsv([['a,b']]))->toBe('"a,b"');
});
