<?php

namespace App\Auth;

class TokenService
{
    public function generate(): string
    {
        return bin2hex(random_bytes(32));
    }
}
