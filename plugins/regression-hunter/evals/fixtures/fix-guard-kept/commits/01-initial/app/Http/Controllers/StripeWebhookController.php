<?php

namespace App\Http\Controllers;

use App\Mail\PaymentReceipt;
use App\Models\Payment;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\Mail;

class StripeWebhookController extends Controller
{
    public function __invoke(Request $request): Response
    {
        $event = $request->json()->all();
        $intent = $event['data']['object'];

        $payment = Payment::create([
            'customer_id' => $intent['metadata']['customer_id'],
            'amount_cents' => $intent['amount_received'],
            'currency' => $intent['currency'],
        ]);

        Mail::to($payment->customer)->send(new PaymentReceipt($payment));

        return response()->noContent();
    }
}
