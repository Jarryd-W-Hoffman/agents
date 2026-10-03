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

Apply invoice-level discounts: `InvoiceService::total` now subtracts the
invoice's `discount_cents` from the sum of its lines.

## impact-scan.py output

```json
{
  "base": "base",
  "head": "head",
  "analyse": true,
  "reason": "code or config changed",
  "files": [
    {
      "path": "app/Services/InvoiceService.php",
      "status": "modified",
      "category": "code",
      "lines_changed": 2
    }
  ],
  "symbols": [
    {
      "id": "S1",
      "symbol": "InvoiceService::total",
      "kind": "method",
      "change": "modified",
      "signature_changed": false,
      "path": "app/Services/InvoiceService.php",
      "line": 9,
      "entry": null,
      "references": [
        {
          "path": "app/Http/Controllers/InvoiceController.php",
          "line": 12,
          "text": "return ['id' => $invoice->id, 'total_cents' => $invoices->total($invoice)];",
          "rev": "head",
          "in_test": false,
          "entry_hint": null
        },
        {
          "path": "app/Jobs/SendInvoiceReminder.php",
          "line": 20,
          "text": "new InvoiceReminder($this->invoice, $invoices->total($this->invoice))",
          "rev": "head",
          "in_test": false,
          "entry_hint": "queue"
        },
        {
          "path": "tests/Unit/InvoiceServiceTest.php",
          "line": 9,
          "text": "expect(app(InvoiceService::class)->total($invoice))->toBe(1000);",
          "rev": "head",
          "in_test": true,
          "entry_hint": null
        }
      ],
      "total_references": 3,
      "truncated": false
    }
  ]
}
```

## Diff

```diff
--- a/app/Services/InvoiceService.php
+++ b/app/Services/InvoiceService.php
@@ -11 +11 @@
-        return $invoice->lines->sum('amount_cents');
+        return $invoice->lines->sum('amount_cents') - $invoice->discount_cents;
```

## Files at head (the whole repository after this change)

### `app/Console/Commands/RemindOverdueInvoices.php`

```php
<?php

namespace App\Console\Commands;

use App\Jobs\SendInvoiceReminder;
use App\Models\Invoice;
use Illuminate\Console\Command;

class RemindOverdueInvoices extends Command
{
    protected $signature = 'invoices:remind';

    public function handle(): void
    {
        Invoice::overdue()->each(fn (Invoice $invoice) => SendInvoiceReminder::dispatch($invoice));
    }
}
```

### `app/Http/Controllers/InvoiceController.php`

```php
<?php

namespace App\Http\Controllers;

use App\Models\Invoice;
use App\Services\InvoiceService;

class InvoiceController extends Controller
{
    public function show(Invoice $invoice, InvoiceService $invoices): array
    {
        return ['id' => $invoice->id, 'total_cents' => $invoices->total($invoice)];
    }
}
```

### `app/Jobs/SendInvoiceReminder.php`

```php
<?php

namespace App\Jobs;

use App\Mail\InvoiceReminder;
use App\Models\Invoice;
use App\Services\InvoiceService;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Support\Facades\Mail;

class SendInvoiceReminder implements ShouldQueue
{
    public function __construct(public Invoice $invoice)
    {
    }

    public function handle(InvoiceService $invoices): void
    {
        Mail::to($this->invoice->customer)->send(
            new InvoiceReminder($this->invoice, $invoices->total($this->invoice))
        );
    }
}
```

### `app/Services/InvoiceService.php`

```php
<?php

namespace App\Services;

use App\Models\Invoice;

class InvoiceService
{
    public function total(Invoice $invoice): int
    {
        return $invoice->lines->sum('amount_cents') - $invoice->discount_cents;
    }
}
```

### `app/Services/TokenService.php`

```php
<?php

namespace App\Services;

class TokenService
{
    public function total(): int
    {
        return count($this->tokens);
    }
}
```

### `routes/console.php`

```php
<?php

use Illuminate\Support\Facades\Schedule;

Schedule::command('invoices:remind')->dailyAt('08:00');
```

### `routes/web.php`

```php
<?php

use App\Http\Controllers\InvoiceController;
use Illuminate\Support\Facades\Route;

Route::get('/invoices/{invoice}', [InvoiceController::class, 'show']);
```

### `tests/Unit/InvoiceServiceTest.php`

```php
<?php

use App\Models\Invoice;
use App\Services\InvoiceService;

it('sums the lines of an invoice', function () {
    $invoice = Invoice::factory()->hasLines(2, ['amount_cents' => 500])->create();

    expect(app(InvoiceService::class)->total($invoice))->toBe(1000);
});
```
