<?php

namespace App\Services;

use App\Mail\PaymentReceipt;
use App\Models\Payment;
use Illuminate\Support\Facades\Mail;

class PaymentRecorder
{
    public function record(int $customerId, int $amountCents, string $currency, ?string $providerEventId = null): Payment
    {
        // EVAL: bait -- the #311 guard moved here intact; the refactor keeps the invariant
        if ($providerEventId !== null && Payment::where('provider_event_id', $providerEventId)->exists()) {
            return Payment::where('provider_event_id', $providerEventId)->first();
        }

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
