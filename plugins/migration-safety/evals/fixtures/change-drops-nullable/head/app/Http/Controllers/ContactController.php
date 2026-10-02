<?php

namespace App\Http\Controllers;

use App\Http\Requests\StoreContactRequest;
use App\Models\Contact;

class ContactController extends Controller
{
    public function store(StoreContactRequest $request): Contact
    {
        // phone is optional on the form
        return Contact::create($request->only('name', 'phone'));
    }
}
