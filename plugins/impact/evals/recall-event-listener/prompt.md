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

Store money as integer cents everywhere: the `OrderPlaced` event now carries
`totalCents` instead of a float `total`.

## impact-scan.py output

```json
{
  "base": "base",
  "head": "head",
  "analyse": true,
  "reason": "code or config changed",
  "files": [
    {
      "path": "app/Events/OrderPlaced.php",
      "status": "modified",
      "category": "code",
      "lines_changed": 2
    },
    {
      "path": "app/Http/Controllers/CheckoutController.php",
      "status": "modified",
      "category": "code",
      "lines_changed": 2
    }
  ],
  "symbols": [
    {
      "id": "S1",
      "symbol": "OrderPlaced::__construct",
      "kind": "method",
      "change": "modified",
      "signature_changed": true,
      "path": "app/Events/OrderPlaced.php",
      "line": 13,
      "entry": null,
      "references": [
        {
          "path": "app/Http/Controllers/CheckoutController.php",
          "line": 5,
          "text": "use App\\Events\\OrderPlaced;",
          "rev": "head",
          "in_test": false,
          "entry_hint": null
        },
        {
          "path": "app/Http/Controllers/CheckoutController.php",
          "line": 14,
          "text": "OrderPlaced::dispatch($order, $order->total_cents);",
          "rev": "head",
          "in_test": false,
          "entry_hint": null
        },
        {
          "path": "app/Providers/EventServiceProvider.php",
          "line": 5,
          "text": "use App\\Events\\OrderPlaced;",
          "rev": "head",
          "in_test": false,
          "entry_hint": "event"
        },
        {
          "path": "app/Providers/EventServiceProvider.php",
          "line": 12,
          "text": "OrderPlaced::class => [",
          "rev": "head",
          "in_test": false,
          "entry_hint": "event"
        }
      ],
      "total_references": 4,
      "truncated": false
    },
    {
      "id": "S2",
      "symbol": "CheckoutController::store",
      "kind": "method",
      "change": "modified",
      "signature_changed": false,
      "path": "app/Http/Controllers/CheckoutController.php",
      "line": 11,
      "entry": "http",
      "references": [
        {
          "path": "routes/web.php",
          "line": 6,
          "text": "Route::post('/checkout', [CheckoutController::class, 'store']);",
          "rev": "head",
          "in_test": false,
          "entry_hint": "http"
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
--- a/app/Events/OrderPlaced.php
+++ b/app/Events/OrderPlaced.php
@@ -13 +13 @@
-    public function __construct(public Order $order, public float $total)
+    public function __construct(public Order $order, public int $totalCents)
--- a/app/Http/Controllers/CheckoutController.php
+++ b/app/Http/Controllers/CheckoutController.php
@@ -14 +14 @@
-        OrderPlaced::dispatch($order, $order->total_cents / 100);
+        OrderPlaced::dispatch($order, $order->total_cents);
```

## Files at head (the whole repository after this change)

### `app/Events/OrderPlaced.php`

```php
<?php

namespace App\Events;

use App\Models\Order;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class OrderPlaced
{
    use Dispatchable, SerializesModels;

    public function __construct(public Order $order, public int $totalCents)
    {
    }
}
```

### `app/Http/Controllers/CheckoutController.php`

```php
<?php

namespace App\Http\Controllers;

use App\Events\OrderPlaced;
use App\Http\Requests\CheckoutRequest;
use App\Models\Order;

class CheckoutController extends Controller
{
    public function store(CheckoutRequest $request): Order
    {
        $order = Order::create($request->validated());
        OrderPlaced::dispatch($order, $order->total_cents);

        return $order;
    }
}
```

### `app/Listeners/SendOrderConfirmation.php`

```php
<?php

namespace App\Listeners;

use App\Mail\OrderConfirmation;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Support\Facades\Mail;

class SendOrderConfirmation implements ShouldQueue
{
    public function handle($event): void
    {
        Mail::to($event->order->customer)->send(new OrderConfirmation($event->order, $event->total));
    }
}
```

### `app/Providers/EventServiceProvider.php`

```php
<?php

namespace App\Providers;

use App\Events\OrderPlaced;
use App\Listeners\SendOrderConfirmation;
use Illuminate\Foundation\Support\Providers\EventServiceProvider as ServiceProvider;

class EventServiceProvider extends ServiceProvider
{
    protected $listen = [
        OrderPlaced::class => [
            SendOrderConfirmation::class,
        ],
    ];
}
```

### `routes/web.php`

```php
<?php

use App\Http\Controllers\CheckoutController;
use Illuminate\Support\Facades\Route;

Route::post('/checkout', [CheckoutController::class, 'store']);
```
