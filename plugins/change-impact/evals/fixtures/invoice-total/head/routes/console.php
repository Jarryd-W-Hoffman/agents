<?php

use Illuminate\Support\Facades\Schedule;

// EVAL: the schedule names the command by its signature string; no name search from total() reaches it
Schedule::command('invoices:remind')->dailyAt('08:00');
