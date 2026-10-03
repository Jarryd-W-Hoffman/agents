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

Invoices need the accounting system's reference so finance can match them.
Add a nullable `reference` column and accept it when creating an invoice.

## find-migrations.py output

```json
{
  "base": "base",
  "head": "head",
  "migrations": [
    {
      "path": "database/migrations/2026_04_01_000000_create_invoices_table.php",
      "status": "modified",
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

- modified `app/Models/Invoice.php`
- modified `database/migrations/2026_04_01_000000_create_invoices_table.php`

## Files at base (what production runs now)

### `app/Models/Invoice.php`

```php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Invoice extends Model
{
    protected $fillable = ['order_id', 'amount_cents'];
}
```

### `database/migrations/2026_04_01_000000_create_invoices_table.php`

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('invoices', function (Blueprint $table) {
            $table->id();
            $table->foreignId('order_id')->constrained();
            $table->unsignedInteger('amount_cents');
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('invoices');
    }
};
```

## Files at head (this change; unchanged files are as at base)

### `app/Models/Invoice.php` (modified)

```php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Invoice extends Model
{
    protected $fillable = ['order_id', 'amount_cents', 'reference'];
}
```

### `database/migrations/2026_04_01_000000_create_invoices_table.php` (modified)

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('invoices', function (Blueprint $table) {
            $table->id();
            $table->foreignId('order_id')->constrained();
            $table->unsignedInteger('amount_cents');
            $table->string('reference')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('invoices');
    }
};
```
