<?php

namespace App\Pdf;

class PdfRenderer
{
    public function generate(string $html): string
    {
        return $this->engine->render($html);
    }
}
