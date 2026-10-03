<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('customers', function (Blueprint $table) {
            $table->dropColumn('legacy_email');
            // EVAL: bait -- looks like the dropped-column defect, but nothing at base references legacy_email
        });
    }

    public function down(): void
    {
        Schema::table('customers', function (Blueprint $table) {
            $table->string('legacy_email')->nullable()->after('email');
        });
    }
};
