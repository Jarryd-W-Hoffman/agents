<?php

namespace App\Http\Controllers;

use App\Events\OrderPlaced;
use App\Http\Requests\CheckoutRequest;
use App\Models\Order;

class CheckoutController extends Controller
{
    public function store(CheckoutRequest $request): Order
    {
        $order = Order::create($request->validated());
        OrderPlaced::dispatch($order, $order->total_cents / 100);

        return $order;
    }
}
