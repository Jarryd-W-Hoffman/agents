<?php

namespace App\Jobs;

use App\Auth\TokenService;
use Illuminate\Contracts\Queue\ShouldQueue;

class RotateApiTokens implements ShouldQueue
{
    // EVAL: bait -- calls TokenService::generate, not Report::generate
    public function handle(TokenService $tokens): void
    {
        User::each(fn ($user) => $user->update(['api_token' => $tokens->generate()]));
    }
}
