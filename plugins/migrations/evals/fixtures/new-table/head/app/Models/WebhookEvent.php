<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class WebhookEvent extends Model
{
    public $timestamps = false;

    protected $fillable = ['customer_id', 'provider', 'provider_event_id', 'payload', 'received_at'];

    protected $casts = ['payload' => 'array', 'received_at' => 'datetime'];
}
