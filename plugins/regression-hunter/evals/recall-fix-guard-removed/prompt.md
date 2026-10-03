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

Move payment recording out of the Stripe webhook controller into a
`PaymentRecorder` service, so the admin "record a manual payment" screen can
reuse it. No behaviour change intended.

## history-scan.py output

```json
{
  "base": "HEAD",
  "head": "working tree",
  "analyse": true,
  "reason": "1 fix or revert commit(s) on the changed lines, 0 revert(s) on the changed files, 0 usual partner file(s) missing",
  "signals": {
    "fix_on_lines": 1,
    "reverts": 0,
    "missing_partners": 0
  },
  "files": [
    {
      "path": "app/Http/Controllers/StripeWebhookController.php",
      "reviewed": true,
      "commits": [
        {
          "sha": "018c50a776b67ce772a26f487f51b7a5884a7022",
          "short": "018c50a",
          "date": "2026-01-03",
          "author": "Dev Example",
          "subject": "Fix double charge when Stripe retries a webhook (#311)",
          "kinds": [
            "fix"
          ],
          "refs": [
            "#311"
          ],
          "on_changed_lines": true
        },
        {
          "sha": "eb2be38ec1b13e1c6ec8133a9d39c5d40f01552b",
          "short": "eb2be38",
          "date": "2026-01-04",
          "author": "Dev Example",
          "subject": "Store currency codes in upper case",
          "kinds": [],
          "refs": [],
          "on_changed_lines": true
        },
        {
          "sha": "010e282456ce1e073fe84d4d7662c087baabe1dc",
          "short": "010e282",
          "date": "2026-01-01",
          "author": "Dev Example",
          "subject": "Add Stripe webhook handler for successful payments",
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
commit 018c50a776b67ce772a26f487f51b7a5884a7022
Date: 2026-01-03

Fix double charge when Stripe retries a webhook (#311)

Stripe retries any webhook it does not get a 2xx for within ten seconds.
When the receipt mail was slow, the retry arrived while the first request
was still running, and the second delivery created a second Payment and
sent a second receipt. Customers saw two charges on their statement.

Record the Stripe event id and skip events already recorded. The unique
index on provider_event_id backs this up at the database.


diff --git a/app/Http/Controllers/StripeWebhookController.php b/app/Http/Controllers/StripeWebhookController.php
index 2ae0baa..f7c63ce 100644
--- a/app/Http/Controllers/StripeWebhookController.php
+++ b/app/Http/Controllers/StripeWebhookController.php
@@ -15,7 +15,12 @@ class StripeWebhookController extends Controller
         $event = $request->json()->all();
         $intent = $event['data']['object'];
 
+        if (Payment::where('provider_event_id', $event['id'])->exists()) {
+            return response()->noContent();
+        }
+
         $payment = Payment::create([
+            'provider_event_id' => $event['id'],
             'customer_id' => $intent['metadata']['customer_id'],
             'amount_cents' => $intent['amount_received'],
             'currency' => $intent['currency'],
diff --git a/tests/Feature/StripeWebhookTest.php b/tests/Feature/StripeWebhookTest.php
new file mode 100644
index 0000000..e9335f4
--- /dev/null
+++ b/tests/Feature/StripeWebhookTest.php
@@ -0,0 +1,12 @@
+<?php
+
+use App\Models\Payment;
+
+it('ignores a retried event', function () {
+    $event = stripeEvent('evt_1', amount: 5000);
+
+    $this->postJson('/api/webhooks/stripe', $event)->assertNoContent();
+    $this->postJson('/api/webhooks/stripe', $event)->assertNoContent();
+
+    expect(Payment::count())->toBe(1);
+});
```

```diff
commit eb2be38ec1b13e1c6ec8133a9d39c5d40f01552b
Date: 2026-01-04

Store currency codes in upper case


diff --git a/app/Http/Controllers/StripeWebhookController.php b/app/Http/Controllers/StripeWebhookController.php
index f7c63ce..7182ea8 100644
--- a/app/Http/Controllers/StripeWebhookController.php
+++ b/app/Http/Controllers/StripeWebhookController.php
@@ -23,7 +23,7 @@ class StripeWebhookController extends Controller
             'provider_event_id' => $event['id'],
             'customer_id' => $intent['metadata']['customer_id'],
             'amount_cents' => $intent['amount_received'],
-            'currency' => $intent['currency'],
+            'currency' => strtoupper($intent['currency']),
         ]);
 
         Mail::to($payment->customer)->send(new PaymentReceipt($payment));
```

```diff
commit 010e282456ce1e073fe84d4d7662c087baabe1dc
Date: 2026-01-01

Add Stripe webhook handler for successful payments


diff --git a/app/Http/Controllers/StripeWebhookController.php b/app/Http/Controllers/StripeWebhookController.php
new file mode 100644
index 0000000..2ae0baa
--- /dev/null
+++ b/app/Http/Controllers/StripeWebhookController.php
@@ -0,0 +1,28 @@
+<?php
+
+namespace App\Http\Controllers;
+
+use App\Mail\PaymentReceipt;
+use App\Models\Payment;
+use Illuminate\Http\Request;
+use Illuminate\Http\Response;
+use Illuminate\Support\Facades\Mail;
+
+class StripeWebhookController extends Controller
+{
+    public function __invoke(Request $request): Response
+    {
+        $event = $request->json()->all();
+        $intent = $event['data']['object'];
+
+        $payment = Payment::create([
+            'customer_id' => $intent['metadata']['customer_id'],
+            'amount_cents' => $intent['amount_received'],
+            'currency' => $intent['currency'],
+        ]);
+
+        Mail::to($payment->customer)->send(new PaymentReceipt($payment));
+
+        return response()->noContent();
+    }
+}
diff --git a/routes/api.php b/routes/api.php
new file mode 100644
index 0000000..945a51c
--- /dev/null
+++ b/routes/api.php
@@ -0,0 +1,6 @@
+<?php
+
+use App\Http\Controllers\StripeWebhookController;
+use Illuminate\Support\Facades\Route;
+
+Route::post('/webhooks/stripe', StripeWebhookController::class);
```

## Diff of the change (tracked files)

```diff
diff --git a/app/Http/Controllers/StripeWebhookController.php b/app/Http/Controllers/StripeWebhookController.php
index 7182ea8..74032fa 100644
--- a/app/Http/Controllers/StripeWebhookController.php
+++ b/app/Http/Controllers/StripeWebhookController.php
@@ -2,31 +2,23 @@
 
 namespace App\Http\Controllers;
 
-use App\Mail\PaymentReceipt;
-use App\Models\Payment;
+use App\Services\PaymentRecorder;
 use Illuminate\Http\Request;
 use Illuminate\Http\Response;
-use Illuminate\Support\Facades\Mail;
 
 class StripeWebhookController extends Controller
 {
-    public function __invoke(Request $request): Response
+    public function __invoke(Request $request, PaymentRecorder $payments): Response
     {
         $event = $request->json()->all();
         $intent = $event['data']['object'];
 
-        if (Payment::where('provider_event_id', $event['id'])->exists()) {
-            return response()->noContent();
-        }
-
-        $payment = Payment::create([
-            'provider_event_id' => $event['id'],
-            'customer_id' => $intent['metadata']['customer_id'],
-            'amount_cents' => $intent['amount_received'],
-            'currency' => strtoupper($intent['currency']),
-        ]);
-
-        Mail::to($payment->customer)->send(new PaymentReceipt($payment));
+        $payments->record(
+            customerId: $intent['metadata']['customer_id'],
+            amountCents: $intent['amount_received'],
+            currency: $intent['currency'],
+            providerEventId: $event['id'],
+        );
 
         return response()->noContent();
     }
```

## Changed files at head

### `app/Http/Controllers/StripeWebhookController.php`

```php
<?php

namespace App\Http\Controllers;

use App\Services\PaymentRecorder;
use Illuminate\Http\Request;
use Illuminate\Http\Response;

class StripeWebhookController extends Controller
{
    public function __invoke(Request $request, PaymentRecorder $payments): Response
    {
        $event = $request->json()->all();
        $intent = $event['data']['object'];

        $payments->record(
            customerId: $intent['metadata']['customer_id'],
            amountCents: $intent['amount_received'],
            currency: $intent['currency'],
            providerEventId: $event['id'],
        );

        return response()->noContent();
    }
}
```

### `app/Services/PaymentRecorder.php` (new, untracked)

```php
<?php

namespace App\Services;

use App\Mail\PaymentReceipt;
use App\Models\Payment;
use Illuminate\Support\Facades\Mail;

class PaymentRecorder
{
    public function record(int $customerId, int $amountCents, string $currency, ?string $providerEventId = null): Payment
    {
        $payment = Payment::create([
            'provider_event_id' => $providerEventId,
            'customer_id' => $customerId,
            'amount_cents' => $amountCents,
            'currency' => strtoupper($currency),
        ]);

        Mail::to($payment->customer)->send(new PaymentReceipt($payment));

        return $payment;
    }
}
```
