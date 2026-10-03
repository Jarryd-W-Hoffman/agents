<?php

namespace App\Services;

class TokenService
{
    // EVAL: name collision -- an unrelated total() that the analyst must not map
    public function total(): int
    {
        return count($this->tokens);
    }
}
