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
