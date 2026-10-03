---
max_turns: 40
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash]
---

Hunt for regressions in the change below.

## History Packet (already resolved -- do not rebuild it)

There is no git repository, no checkout and no files on disk: nothing to clone,
fetch, glob, `ls` or `git` at. Skip Steps 1 and 2 of the skill entirely. The
target is resolved and `history-scan.py` has already run; its output is below.
Act on it exactly as Step 2 says: if `analyse` is false, stop there. Otherwise
go straight to Step 3, and brief the reviewer with everything below in place
of `git` commands: the `git show` output of every commit the scan lists, the
diff, and the changed files at head.

Time spent looking for files is time not spent reviewing, and there is nothing
to find.

Use the regressions skill.

## Change intent

Add a "Clear invoice cache" action for admins that flushes every cached
invoice at once, instead of forgetting them one by one.

## history-scan.py output

```json
{
  "base": "HEAD",
  "head": "working tree",
  "analyse": true,
  "reason": "1 fix or revert commit(s) on the changed lines, 1 revert(s) on the changed files, 0 usual partner file(s) missing",
  "signals": {
    "fix_on_lines": 1,
    "reverts": 1,
    "missing_partners": 0
  },
  "files": [
    {
      "path": "app/Services/InvoiceCache.php",
      "reviewed": true,
      "commits": [
        {
          "sha": "fcacd17f885f666be56aa8b87d44ddeeec78170c",
          "short": "fcacd17",
          "date": "2026-01-03",
          "author": "Dev Example",
          "subject": "Revert \"Use cache tags so all invoice entries can be flushed at once\"",
          "kinds": [
            "revert"
          ],
          "refs": [
            "INC-142"
          ],
          "reverts": "9cd444270bcb2adbef2490388623f72b23de4178",
          "on_changed_lines": true
        },
        {
          "sha": "9cd444270bcb2adbef2490388623f72b23de4178",
          "short": "9cd4442",
          "date": "2026-01-02",
          "author": "Dev Example",
          "subject": "Use cache tags so all invoice entries can be flushed at once",
          "kinds": [],
          "refs": [],
          "on_changed_lines": true
        },
        {
          "sha": "4b130509c89a1a97276bf1268a19692c23a299a7",
          "short": "4b13050",
          "date": "2026-01-01",
          "author": "Dev Example",
          "subject": "Cache invoices for an hour",
          "kinds": [],
          "refs": [],
          "on_changed_lines": true
        }
      ],
      "missing_partners": [],
      "history_commits": 3
    }
  ]
}
```

## The commits the scan lists (git show)

```diff
commit fcacd17f885f666be56aa8b87d44ddeeec78170c
Date: 2026-01-03

Revert "Use cache tags so all invoice entries can be flushed at once"

This reverts commit 9cd444270bcb2adbef2490388623f72b23de4178.

Production uses the file cache store, which does not support tags. Every
invoice page threw BadMethodCallException ("This cache store does not
support tagging") from the moment this deployed until it was rolled back.
INC-142.


diff --git a/app/Services/InvoiceCache.php b/app/Services/InvoiceCache.php
index 3e18693..51222f1 100644
--- a/app/Services/InvoiceCache.php
+++ b/app/Services/InvoiceCache.php
@@ -9,16 +9,11 @@ class InvoiceCache
 {
     public function get(int $id): Invoice
     {
-        return Cache::tags(['invoices'])->remember("invoice:{$id}", 3600, fn () => Invoice::with('lines')->findOrFail($id));
+        return Cache::remember("invoice:{$id}", 3600, fn () => Invoice::with('lines')->findOrFail($id));
     }
 
     public function forget(int $id): void
     {
-        Cache::tags(['invoices'])->forget("invoice:{$id}");
-    }
-
-    public function flushAll(): void
-    {
-        Cache::tags(['invoices'])->flush();
+        Cache::forget("invoice:{$id}");
     }
 }
```

```diff
commit 9cd444270bcb2adbef2490388623f72b23de4178
Date: 2026-01-02

Use cache tags so all invoice entries can be flushed at once


diff --git a/app/Services/InvoiceCache.php b/app/Services/InvoiceCache.php
index 51222f1..3e18693 100644
--- a/app/Services/InvoiceCache.php
+++ b/app/Services/InvoiceCache.php
@@ -9,11 +9,16 @@ class InvoiceCache
 {
     public function get(int $id): Invoice
     {
-        return Cache::remember("invoice:{$id}", 3600, fn () => Invoice::with('lines')->findOrFail($id));
+        return Cache::tags(['invoices'])->remember("invoice:{$id}", 3600, fn () => Invoice::with('lines')->findOrFail($id));
     }
 
     public function forget(int $id): void
     {
-        Cache::forget("invoice:{$id}");
+        Cache::tags(['invoices'])->forget("invoice:{$id}");
+    }
+
+    public function flushAll(): void
+    {
+        Cache::tags(['invoices'])->flush();
     }
 }
```

```diff
commit 4b130509c89a1a97276bf1268a19692c23a299a7
Date: 2026-01-01

Cache invoices for an hour


diff --git a/app/Services/InvoiceCache.php b/app/Services/InvoiceCache.php
new file mode 100644
index 0000000..51222f1
--- /dev/null
+++ b/app/Services/InvoiceCache.php
@@ -0,0 +1,19 @@
+<?php
+
+namespace App\Services;
+
+use App\Models\Invoice;
+use Illuminate\Support\Facades\Cache;
+
+class InvoiceCache
+{
+    public function get(int $id): Invoice
+    {
+        return Cache::remember("invoice:{$id}", 3600, fn () => Invoice::with('lines')->findOrFail($id));
+    }
+
+    public function forget(int $id): void
+    {
+        Cache::forget("invoice:{$id}");
+    }
+}
diff --git a/config/cache.php b/config/cache.php
new file mode 100644
index 0000000..a70ab8e
--- /dev/null
+++ b/config/cache.php
@@ -0,0 +1,5 @@
+<?php
+
+return [
+    'default' => env('CACHE_STORE', 'file'),
+];
```

## Diff of the change (tracked files)

```diff
diff --git a/app/Services/InvoiceCache.php b/app/Services/InvoiceCache.php
index 51222f1..3e18693 100644
--- a/app/Services/InvoiceCache.php
+++ b/app/Services/InvoiceCache.php
@@ -9,11 +9,16 @@ class InvoiceCache
 {
     public function get(int $id): Invoice
     {
-        return Cache::remember("invoice:{$id}", 3600, fn () => Invoice::with('lines')->findOrFail($id));
+        return Cache::tags(['invoices'])->remember("invoice:{$id}", 3600, fn () => Invoice::with('lines')->findOrFail($id));
     }
 
     public function forget(int $id): void
     {
-        Cache::forget("invoice:{$id}");
+        Cache::tags(['invoices'])->forget("invoice:{$id}");
+    }
+
+    public function flushAll(): void
+    {
+        Cache::tags(['invoices'])->flush();
     }
 }
```

## Changed files at head

### `app/Services/InvoiceCache.php`

```php
<?php

namespace App\Services;

use App\Models\Invoice;
use Illuminate\Support\Facades\Cache;

class InvoiceCache
{
    public function get(int $id): Invoice
    {
        return Cache::tags(['invoices'])->remember("invoice:{$id}", 3600, fn () => Invoice::with('lines')->findOrFail($id));
    }

    public function forget(int $id): void
    {
        Cache::tags(['invoices'])->forget("invoice:{$id}");
    }

    public function flushAll(): void
    {
        Cache::tags(['invoices'])->flush();
    }
}
```
