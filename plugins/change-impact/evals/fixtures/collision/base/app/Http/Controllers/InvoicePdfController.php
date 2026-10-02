<?php

namespace App\Http\Controllers;

use App\Pdf\PdfRenderer;

class InvoicePdfController extends Controller
{
    // EVAL: bait -- calls PdfRenderer::generate, not Report::generate
    public function show(Invoice $invoice, PdfRenderer $pdf): string
    {
        return $pdf->generate(view('invoices.pdf', compact('invoice'))->render());
    }
}
