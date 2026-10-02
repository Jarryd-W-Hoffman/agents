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

Record inbound payment-provider webhooks so they can be replayed. New
`webhook_events` table, written by the webhook controller.

## find-migrations.py output

```json
{
  "base": "base",
  "head": "head",
  "migrations": [
    {
      "path": "database/migrations/2026_10_01_120000_create_webhook_events_table.php",
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

- added `app/Http/Controllers/WebhookController.php`
- added `app/Models/WebhookEvent.php`
- added `database/migrations/2026_10_01_120000_create_webhook_events_table.php`

## Files at base (what production runs now)

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

### `app/Http/Controllers/WebhookController.php` (added)

```php
<?php

namespace App\Http\Controllers;

use App\Models\WebhookEvent;
use Illuminate\Http\Request;
use Illuminate\Http\Response;

class WebhookController extends Controller
{
    public function __invoke(Request $request, string $provider): Response
    {
        WebhookEvent::firstOrCreate(
            ['provider' => $provider, 'provider_event_id' => (string) $request->input('id')],
            ['payload' => $request->all(), 'received_at' => now()],
        );

        return response()->noContent();
    }
}
```

### `app/Models/WebhookEvent.php` (added)

```php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class WebhookEvent extends Model
{
    public $timestamps = false;

    protected $fillable = ['customer_id', 'provider', 'provider_event_id', 'payload', 'received_at'];

    protected $casts = ['payload' => 'array', 'received_at' => 'datetime'];
}
```

### `database/migrations/2026_10_01_120000_create_webhook_events_table.php` (added)

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('webhook_events', function (Blueprint $table) {
            $table->id();
            $table->foreignId('customer_id')->nullable()->constrained()->nullOnDelete();
            $table->string('provider', 32);
            $table->string('provider_event_id');
            $table->json('payload');
            $table->timestamp('received_at');
            $table->unique(['provider', 'provider_event_id']);
            $table->index('received_at');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('webhook_events');
    }
};
```
