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

Phone numbers are stored in E.164 form, at most 15 digits plus a leading `+`.
Shorten `contacts.phone` from 255 to 32 characters to match.

## find-migrations.py output

```json
{
  "base": "base",
  "head": "head",
  "migrations": [
    {
      "path": "database/migrations/2026_10_01_110000_shorten_phone_on_contacts.php",
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

- added `database/migrations/2026_10_01_110000_shorten_phone_on_contacts.php`

## Files at base (what production runs now)

### `app/Http/Controllers/ContactController.php`

```php
<?php

namespace App\Http\Controllers;

use App\Http\Requests\StoreContactRequest;
use App\Models\Contact;

class ContactController extends Controller
{
    public function store(StoreContactRequest $request): Contact
    {
        // phone is optional on the form
        return Contact::create($request->only('name', 'phone'));
    }
}
```

### `composer.json`

```json
{
    "name": "acme/crm",
    "require": {
        "php": "^8.3",
        "laravel/framework": "^11.9"
    }
}
```

### `database/migrations/2026_03_01_000000_create_contacts_table.php`

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('contacts', function (Blueprint $table) {
            $table->id();
            $table->string('name');
            $table->string('phone')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('contacts');
    }
};
```

## Files at head (this change; unchanged files are as at base)

### `database/migrations/2026_10_01_110000_shorten_phone_on_contacts.php` (added)

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('contacts', function (Blueprint $table) {
            $table->string('phone', 32)->change();
        });
    }

    public function down(): void
    {
        Schema::table('contacts', function (Blueprint $table) {
            $table->string('phone')->nullable()->change();
        });
    }
};
```
