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

Use the regression-hunter skill.

## Change intent

Show the customer's company name on the invoice PDF header.

## history-scan.py output

```json
{
  "base": "HEAD",
  "head": "working tree",
  "analyse": false,
  "reason": "no fix or revert touched the changed lines, no revert touched the files, no usual partner is missing",
  "signals": {
    "fix_on_lines": 0,
    "reverts": 0,
    "missing_partners": 0
  },
  "files": [
    {
      "path": "app/Pdf/InvoicePdf.php",
      "reviewed": true,
      "commits": [
        {
          "sha": "e0fb16f39fa968b56a4c1b176116ab73cfc57b02",
          "short": "e0fb16f",
          "date": "2026-01-02",
          "author": "Dev Example",
          "subject": "Add the customer name to the invoice PDF header",
          "kinds": [],
          "refs": [],
          "on_changed_lines": true
        },
        {
          "sha": "2d3a611b026ccabe52e4dff22888b3d5326022c2",
          "short": "2d3a611",
          "date": "2026-01-01",
          "author": "Dev Example",
          "subject": "Render invoices as PDF",
          "kinds": [],
          "refs": [],
          "on_changed_lines": true
        }
      ],
      "missing_partners": [],
      "history_commits": 2
    }
  ]
}
```

## The commits the scan lists (git show)

```diff
commit e0fb16f39fa968b56a4c1b176116ab73cfc57b02
Date: 2026-01-02

Add the customer name to the invoice PDF header


diff --git a/app/Pdf/InvoicePdf.php b/app/Pdf/InvoicePdf.php
index 9c501f4..8380582 100644
--- a/app/Pdf/InvoicePdf.php
+++ b/app/Pdf/InvoicePdf.php
@@ -11,6 +11,7 @@ class InvoicePdf
         return [
             'number' => $invoice->number,
             'date' => $invoice->issued_at->toDateString(),
+            'customer' => $invoice->customer->name,
         ];
     }
 }
```

```diff
commit 2d3a611b026ccabe52e4dff22888b3d5326022c2
Date: 2026-01-01

Render invoices as PDF


diff --git a/app/Pdf/InvoicePdf.php b/app/Pdf/InvoicePdf.php
new file mode 100644
index 0000000..9c501f4
--- /dev/null
+++ b/app/Pdf/InvoicePdf.php
@@ -0,0 +1,16 @@
+<?php
+
+namespace App\Pdf;
+
+use App\Models\Invoice;
+
+class InvoicePdf
+{
+    public function header(Invoice $invoice): array
+    {
+        return [
+            'number' => $invoice->number,
+            'date' => $invoice->issued_at->toDateString(),
+        ];
+    }
+}
```

## Diff of the change (tracked files)

```diff
diff --git a/app/Pdf/InvoicePdf.php b/app/Pdf/InvoicePdf.php
index 8380582..1a7ebb4 100644
--- a/app/Pdf/InvoicePdf.php
+++ b/app/Pdf/InvoicePdf.php
@@ -12,6 +12,7 @@ class InvoicePdf
             'number' => $invoice->number,
             'date' => $invoice->issued_at->toDateString(),
             'customer' => $invoice->customer->name,
+            'company' => $invoice->customer->company_name,
         ];
     }
 }
```

## Changed files at head

### `app/Pdf/InvoicePdf.php`

```php
<?php

namespace App\Pdf;

use App\Models\Invoice;

class InvoicePdf
{
    public function header(Invoice $invoice): array
    {
        return [
            'number' => $invoice->number,
            'date' => $invoice->issued_at->toDateString(),
            'customer' => $invoice->customer->name,
            'company' => $invoice->customer->company_name,
        ];
    }
}
```
