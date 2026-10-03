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

Monthly reports include refunds: `Report::generate` now subtracts refunded
amounts from each day's revenue.

## impact-scan.py output

```json
{
  "base": "base",
  "head": "head",
  "analyse": true,
  "reason": "code or config changed",
  "files": [
    {
      "path": "app/Reports/Report.php",
      "status": "modified",
      "category": "code",
      "lines_changed": 2
    }
  ],
  "symbols": [
    {
      "id": "S1",
      "symbol": "Report::generate",
      "kind": "method",
      "change": "modified",
      "signature_changed": false,
      "path": "app/Reports/Report.php",
      "line": 7,
      "entry": null,
      "references": [
        {
          "path": "app/Console/Commands/MakeInvite.php",
          "line": 14,
          "text": "$this->line(url('/invite/'.$tokens->generate()));",
          "rev": "head",
          "in_test": false,
          "entry_hint": "console"
        },
        {
          "path": "app/Http/Controllers/InvoicePdfController.php",
          "line": 11,
          "text": "return $pdf->generate(view('invoices.pdf', compact('invoice'))->render());",
          "rev": "head",
          "in_test": false,
          "entry_hint": null
        },
        {
          "path": "app/Http/Controllers/ReportController.php",
          "line": 11,
          "text": "return $report->generate($month);",
          "rev": "head",
          "in_test": false,
          "entry_hint": null
        },
        {
          "path": "app/Jobs/RotateApiTokens.php",
          "line": 12,
          "text": "User::each(fn ($user) => $user->update(['api_token' => $tokens->generate()]));",
          "rev": "head",
          "in_test": false,
          "entry_hint": "queue"
        }
      ],
      "total_references": 4,
      "truncated": false
    }
  ]
}
```

## Diff

```diff
--- a/app/Reports/Report.php
+++ b/app/Reports/Report.php
@@ -9 +9 @@
-        return $this->days($month)->map(fn ($day) => $day->revenue)->all();
+        return $this->days($month)->map(fn ($day) => $day->revenue - $day->refunds)->all();
```

## Files at head (the whole repository after this change)

### `app/Auth/TokenService.php`

```php
<?php

namespace App\Auth;

class TokenService
{
    public function generate(): string
    {
        return bin2hex(random_bytes(32));
    }
}
```

### `app/Console/Commands/MakeInvite.php`

```php
<?php

namespace App\Console\Commands;

use App\Auth\TokenService;
use Illuminate\Console\Command;

class MakeInvite extends Command
{
    protected $signature = 'invites:make';

    public function handle(TokenService $tokens): void
    {
        $this->line(url('/invite/'.$tokens->generate()));
    }
}
```

### `app/Http/Controllers/InvoicePdfController.php`

```php
<?php

namespace App\Http\Controllers;

use App\Pdf\PdfRenderer;

class InvoicePdfController extends Controller
{
    public function show(Invoice $invoice, PdfRenderer $pdf): string
    {
        return $pdf->generate(view('invoices.pdf', compact('invoice'))->render());
    }
}
```

### `app/Http/Controllers/ReportController.php`

```php
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
```

### `app/Jobs/RotateApiTokens.php`

```php
<?php

namespace App\Jobs;

use App\Auth\TokenService;
use Illuminate\Contracts\Queue\ShouldQueue;

class RotateApiTokens implements ShouldQueue
{
    public function handle(TokenService $tokens): void
    {
        User::each(fn ($user) => $user->update(['api_token' => $tokens->generate()]));
    }
}
```

### `app/Pdf/PdfRenderer.php`

```php
<?php

namespace App\Pdf;

class PdfRenderer
{
    public function generate(string $html): string
    {
        return $this->engine->render($html);
    }
}
```

### `app/Reports/Report.php`

```php
<?php

namespace App\Reports;

class Report
{
    public function generate(string $month): array
    {
        return $this->days($month)->map(fn ($day) => $day->revenue - $day->refunds)->all();
    }
}
```

### `routes/web.php`

```php
<?php

use App\Http\Controllers\ReportController;
use App\Http\Controllers\InvoicePdfController;
use Illuminate\Support\Facades\Route;

Route::get('/reports/{month}', [ReportController::class, 'show']);
Route::get('/invoices/{invoice}/pdf', [InvoicePdfController::class, 'show']);
```
