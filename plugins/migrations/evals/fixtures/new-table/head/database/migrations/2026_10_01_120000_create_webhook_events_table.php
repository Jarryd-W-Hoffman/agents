<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // EVAL: bait -- index, unique and foreign key all on a table created empty in this migration
        Schema::create('webhook_events', function (Blueprint $table) {
            $table->id();
            $table->foreignId('customer_id')->nullable()->constrained()->nullOnDelete();
            $table->string('provider', 32);
            $table->string('provider_event_id');
            $table->json('payload');
            $table->timestamp('received_at');
            $table->unique(['provider', 'provider_event_id']);
            $table->index('received_at');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('webhook_events');
    }
};
