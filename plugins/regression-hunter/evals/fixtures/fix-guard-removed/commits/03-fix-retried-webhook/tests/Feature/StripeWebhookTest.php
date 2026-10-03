<?php

use App\Models\Payment;

it('ignores a retried event', function () {
    $event = stripeEvent('evt_1', amount: 5000);

    $this->postJson('/api/webhooks/stripe', $event)->assertNoContent();
    $this->postJson('/api/webhooks/stripe', $event)->assertNoContent();

    expect(Payment::count())->toBe(1);
});
