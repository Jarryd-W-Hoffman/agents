---
max_turns: 40
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash]
---

Map the impact of the change below.

## Impact Packet (already resolved -- do not rebuild it)

There is no git repository, no checkout and no files on disk: nothing to clone,
fetch, glob, `ls` or `git` at. Skip Steps 1 and 2 of the skill entirely. The
target is resolved and `impact-scan.py` has already run; its output is below.
Act on it exactly as Step 2 says: if `analyse` is false, stop there. Otherwise
go straight to Step 3, and brief the analyst with the files below in place of
`git` commands. The files at head are the whole repository.

Time spent looking for files is time not spent analysing, and there is nothing
to find.

Use the impact skill.

## Change intent

Quote every CSV field in report exports, so customer names containing commas
no longer split into two columns.

## impact-scan.py output

```json
{
  "base": "base",
  "head": "head",
  "analyse": true,
  "reason": "code or config changed",
  "files": [
    {
      "path": "app/Reports/ReportExporter.php",
      "status": "modified",
      "category": "code",
      "lines_changed": 2
    }
  ],
  "symbols": [
    {
      "id": "S1",
      "symbol": "ReportExporter::toCsv",
      "kind": "method",
      "change": "modified",
      "signature_changed": false,
      "path": "app/Reports/ReportExporter.php",
      "line": 7,
      "entry": null,
      "references": [
        {
          "path": "app/Console/Commands/ExportReports.php",
          "line": 17,
          "text": "Storage::put(\"reports/{$this->argument('month')}.csv\", $exporter->toCsv($rows));",
          "rev": "head",
          "in_test": false,
          "entry_hint": "console"
        }
      ],
      "total_references": 1,
      "truncated": false
    }
  ]
}
```

## Diff

```diff
--- a/app/Reports/ReportExporter.php
+++ b/app/Reports/ReportExporter.php
@@ -9 +9 @@
-        return implode("\n", array_map(fn (array $row) => implode(',', $row), $rows));
+        return implode("\n", array_map(fn (array $row) => implode(',', array_map(fn ($v) => '"'.str_replace('"', '""', (string) $v).'"', $row)), $rows));
```

## Files at head (the whole repository after this change)

### `app/Console/Commands/ExportReports.php`

```php
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
        Storage::put("reports/{$this->argument('month')}.csv", $exporter->toCsv($rows));
    }
}
```

### `app/Reports/ReportExporter.php`

```php
<?php

namespace App\Reports;

class ReportExporter
{
    public function toCsv(array $rows): string
    {
        return implode("\n", array_map(fn (array $row) => implode(',', array_map(fn ($v) => '"'.str_replace('"', '""', (string) $v).'"', $row)), $rows));
    }
}
```

### `tests/Unit/SalesReportTest.php`

```php
<?php

use App\Reports\SalesReport;

it('groups rows by day', function () {
    expect(SalesReport::forMonth('2026-09')->rows())->toBeArray();
});
```
