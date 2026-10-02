<?php

use App\Reports\SalesReport;

it('groups rows by day', function () {
    expect(SalesReport::forMonth('2026-09')->rows())->toBeArray();
});
