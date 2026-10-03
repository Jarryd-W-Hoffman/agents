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

Use the change-impact skill.

## Change intent

Document the reporting commands and add a test for the CSV quoting.

## impact-scan.py output

```json
{
  "base": "base",
  "head": "head",
  "analyse": false,
  "reason": "only doc, test changed",
  "files": [
    {
      "path": "README.md",
      "status": "modified",
      "category": "doc",
      "lines_changed": 4
    },
    {
      "path": "tests/Unit/ReportExporterTest.php",
      "status": "added",
      "category": "test",
      "lines_changed": 7
    }
  ],
  "symbols": []
}
```

## Diff

```diff
--- a/README.md
+++ b/README.md
@@ -3,0 +4,4 @@
+
+## Reports
+
+`php artisan reports:export 2026-09` writes a CSV to storage.
--- /dev/null
+++ b/tests/Unit/ReportExporterTest.php
@@ -0,0 +1,7 @@
+<?php
+
+use App\Reports\ReportExporter;
+
+it('quotes fields', function () {
+    expect((new ReportExporter)->toCsv([['a,b']]))->toBe('"a,b"');
+});
```

## Files at head (the whole repository after this change)

### `README.md`

```markdown
# Acme

Internal billing.

## Reports

`php artisan reports:export 2026-09` writes a CSV to storage.
```

### `app/Reports/ReportExporter.php`

```php
<?php

namespace App\Reports;

class ReportExporter
{
    public function toCsv(array $rows): string
    {
        return implode("\n", array_map(fn (array $row) => implode(',', $row), $rows));
    }
}
```

### `tests/Unit/ReportExporterTest.php`

```php
<?php

use App\Reports\ReportExporter;

it('quotes fields', function () {
    expect((new ReportExporter)->toCsv([['a,b']]))->toBe('"a,b"');
});
```
