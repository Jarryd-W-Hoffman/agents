<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('contacts', function (Blueprint $table) {
            // EVAL: seeded defect -- Laravel 11 change() drops the unrestated nullable(), so phone becomes NOT NULL
            $table->string('phone', 32)->change();
        });
    }

    public function down(): void
    {
        Schema::table('contacts', function (Blueprint $table) {
            $table->string('phone')->nullable()->change();
        });
    }
};
