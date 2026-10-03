<?php

namespace App\Listeners;

use App\Mail\OrderConfirmation;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Support\Facades\Mail;

// EVAL: queued listener still reads $event->total; events serialized before the deploy carry the old shape
class SendOrderConfirmation implements ShouldQueue
{
    public function handle($event): void
    {
        Mail::to($event->order->customer)->send(new OrderConfirmation($event->order, $event->total));
    }
}
