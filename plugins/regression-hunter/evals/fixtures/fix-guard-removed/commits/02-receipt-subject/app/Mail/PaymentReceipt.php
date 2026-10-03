<?php

namespace App\Mail;

use App\Models\Payment;
use Illuminate\Mail\Mailable;

class PaymentReceipt extends Mailable
{
    public function __construct(public Payment $payment)
    {
    }

    public function build(): self
    {
        return $this->subject('Payment received: '.number_format($this->payment->amount_cents / 100, 2))
            ->view('mail.receipt');
    }
}
