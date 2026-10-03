<?php

use App\Http\Controllers\StripeWebhookController;
use Illuminate\Support\Facades\Route;

Route::post('/webhooks/stripe', StripeWebhookController::class);
