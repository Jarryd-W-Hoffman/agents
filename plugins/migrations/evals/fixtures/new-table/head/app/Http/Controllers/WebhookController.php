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
