<?php

namespace App\Http\Controllers;

use App\Http\Requests\CheckoutRequest;
use App\Models\Order;

class CheckoutController extends Controller
{
    public function store(CheckoutRequest $request): Order
    {
        return Order::create([
            'customer_id' => $request->user()->customer_id,
            'total_cents' => $request->integer('total_cents'),
            'currency' => $request->input('currency', 'AUD'),
        ]);
    }
}
