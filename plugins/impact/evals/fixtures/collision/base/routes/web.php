<?php

use App\Http\Controllers\ReportController;
use App\Http\Controllers\InvoicePdfController;
use Illuminate\Support\Facades\Route;

Route::get('/reports/{month}', [ReportController::class, 'show']);
Route::get('/invoices/{invoice}/pdf', [InvoicePdfController::class, 'show']);
