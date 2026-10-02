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

Use the migration-safety skill.

## Change intent

Remove `customers.legacy_email`. It was superseded by `email` in the March
cutover and every customer now has `email` set.

- Drop the column.
- Stop reading it in `CustomerController::show` and writing it in `store`.
- Remove it from the model's fillable fields.

## find-migrations.py output

```json
{
  "base": "base",
  "head": "head",
  "migrations": [
    {
      "path": "database/migrations/2026_10_01_090000_drop_legacy_email_from_customers.php",
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

- modified `app/Http/Controllers/CustomerController.php`
- modified `app/Models/Customer.php`
- added `database/migrations/2026_10_01_090000_drop_legacy_email_from_customers.php`

## Files at base (what production runs now)

### `app/Http/Controllers/CustomerController.php`

```php
<?php

namespace App\Http\Controllers;

use App\Http\Requests\StoreCustomerRequest;
use App\Models\Customer;

class CustomerController extends Controller
{
    public function show(Customer $customer): array
    {
        return [
            'id' => $customer->id,
            'name' => $customer->name,
            'email' => $customer->legacy_email ?? $customer->email,
        ];
    }

    public function store(StoreCustomerRequest $request): Customer
    {
        return Customer::create([
            'name' => $request->input('name'),
            'email' => $request->input('email'),
            'legacy_email' => $request->input('email'),
        ]);
    }
}
```

### `app/Models/Customer.php`

```php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Customer extends Model
{
    protected $fillable = ['name', 'email', 'legacy_email'];
}
```

### `database/migrations/2026_01_10_000000_create_customers_table.php`

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('customers', function (Blueprint $table) {
            $table->id();
            $table->string('name');
            $table->string('email')->unique();
            $table->string('legacy_email')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('customers');
    }
};
```

## Files at head (this change; unchanged files are as at base)

### `app/Http/Controllers/CustomerController.php` (modified)

```php
<?php

namespace App\Http\Controllers;

use App\Http\Requests\StoreCustomerRequest;
use App\Models\Customer;

class CustomerController extends Controller
{
    public function show(Customer $customer): array
    {
        return [
            'id' => $customer->id,
            'name' => $customer->name,
            'email' => $customer->email,
        ];
    }

    public function store(StoreCustomerRequest $request): Customer
    {
        return Customer::create([
            'name' => $request->input('name'),
            'email' => $request->input('email'),
        ]);
    }
}
```

### `app/Models/Customer.php` (modified)

```php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Customer extends Model
{
    protected $fillable = ['name', 'email'];
}
```

### `database/migrations/2026_10_01_090000_drop_legacy_email_from_customers.php` (added)

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('customers', function (Blueprint $table) {
            $table->dropColumn('legacy_email');
        });
    }

    public function down(): void
    {
        Schema::table('customers', function (Blueprint $table) {
            $table->string('legacy_email')->nullable()->after('email');
        });
    }
};
```
