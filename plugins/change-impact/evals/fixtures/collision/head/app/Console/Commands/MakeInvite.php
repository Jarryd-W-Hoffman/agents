<?php

namespace App\Console\Commands;

use App\Auth\TokenService;
use Illuminate\Console\Command;

class MakeInvite extends Command
{
    protected $signature = 'invites:make';

    public function handle(TokenService $tokens): void
    {
        $this->line(url('/invite/'.$tokens->generate()));
    }
}
