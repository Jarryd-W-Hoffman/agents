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
