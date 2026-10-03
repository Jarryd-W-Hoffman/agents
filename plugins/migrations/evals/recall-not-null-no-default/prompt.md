---
max_turns: 40
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash]
---

Run a migration safety check of the change below.

## Migration Packet (already resolved -- do not rebuild it)

There is no git repository, no checkout and no files on disk: nothing to clone,
fetch, glob, `ls` or `git` at. Skip Steps 1 and 2 of the skill entirely. The
target is resolved and `find-migrations.py` has already run; its output is
below. Act on it exactly as Step 2 says: if it lists no migrations, stop there.
Otherwise go straight to Step 3, and brief the reviewer with the files below in
place of `git` commands. Base is the revision production runs now; head is
this change.

Time spent looking for files is time not spent reviewing, and there is nothing
to find.

Use the migrations skill.

## Change intent

Support multi-currency checkout: store each order's ISO 4217 currency code.
Checkout passes the currency the customer chose, defaulting to AUD.

## find-migrations.py output

```json
{
  "base": "base",
  "head": "head",
  "migrations": [
    {
      "path": "database/migrations/2026_10_01_100000_add_currency_to_orders.php",
      "status": "added",
      "framework": "laravel"
    }
  ],
  "frameworks": [
    "laravel"
  ],
  "schema_files": [],
  "deploy_files": [],
  "rule_files": []
}
```

## Changed files

- modified `app/Http/Controllers/CheckoutController.php`
- modified `app/Models/Order.php`
- added `database/migrations/2026_10_01_100000_add_currency_to_orders.php`

## Files at base (what production runs now)

### `app/Http/Controllers/CheckoutController.php`

```php
<?php

namespace App\Http\Controllers;

use App\Http\Requests\CheckoutRequest;
use App\Models\Order;

class CheckoutController extends Controller
{
    public function store(CheckoutRequest $request): Order
    {
        return Order::create([
            'customer_id' => $request->user()->customer_id,
            'total_cents' => $request->integer('total_cents'),
        ]);
    }
}
```

### `app/Models/Order.php`

```php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Order extends Model
{
    protected $fillable = ['customer_id', 'total_cents'];
}
```

### `database/migrations/2026_02_01_000000_create_orders_table.php`

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('orders', function (Blueprint $table) {
            $table->id();
            $table->foreignId('customer_id')->constrained();
            $table->unsignedInteger('total_cents');
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('orders');
    }
};
```

## Files at head (this change; unchanged files are as at base)

### `app/Http/Controllers/CheckoutController.php` (modified)

```php
<?php

namespace App\Http\Controllers;

use App\Http\Requests\CheckoutRequest;
use App\Models\Order;

class CheckoutController extends Controller
{
    public function store(CheckoutRequest $request): Order
    {
        return Order::create([
            'customer_id' => $request->user()->customer_id,
            'total_cents' => $request->integer('total_cents'),
            'currency' => $request->input('currency', 'AUD'),
        ]);
    }
}
```

### `app/Models/Order.php` (modified)

```php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Order extends Model
{
    protected $fillable = ['customer_id', 'total_cents', 'currency'];
}
```

### `database/migrations/2026_10_01_100000_add_currency_to_orders.php` (added)

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('orders', function (Blueprint $table) {
            $table->char('currency', 3)->after('total_cents');
        });
    }

    public function down(): void
    {
        Schema::table('orders', function (Blueprint $table) {
            $table->dropColumn('currency');
        });
    }
};
```
